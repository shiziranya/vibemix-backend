#!/usr/bin/env python3
"""
调酒日记功能 - API 测试脚本

测试所有日记相关 API 接口的功能和性能
"""

import requests
import json
import time
from datetime import datetime, timedelta

# 配置
API_BASE_URL = "http://localhost:5000"
TEST_USER_PHONE = "13800138000"
TEST_USER_PASSWORD = "test123"

class DiaryAPITester:
    def __init__(self):
        self.base_url = API_BASE_URL
        self.token = None
        self.test_results = []
        
    def log_test(self, test_name, passed, message="", duration=0):
        """记录测试结果"""
        status = "✓ PASS" if passed else "✗ FAIL"
        result = {
            "test": test_name,
            "status": status,
            "message": message,
            "duration_ms": round(duration * 1000, 2)
        }
        self.test_results.append(result)
        print(f"{status} | {test_name} | {message} ({duration*1000:.2f}ms)")
        
    def login(self):
        """登录获取 JWT token"""
        print("\n[1] 测试登录...")
        start = time.time()
        
        try:
            response = requests.post(
                f"{self.base_url}/api/auth/login",
                json={
                    "phone": TEST_USER_PHONE,
                    "password": TEST_USER_PASSWORD
                }
            )
            duration = time.time() - start
            
            if response.status_code == 200:
                data = response.json()
                self.token = data['data']['access_token']
                self.log_test("用户登录", True, "获取 token 成功", duration)
                return True
            else:
                self.log_test("用户登录", False, f"状态码: {response.status_code}", duration)
                return False
                
        except Exception as e:
            self.log_test("用户登录", False, f"异常: {str(e)}", time.time() - start)
            return False
    
    def test_calendar_api(self):
        """测试日历接口"""
        print("\n[2] 测试日历接口...")
        
        # 获取当前年月
        now = datetime.now()
        year = now.year
        month = now.month
        
        start = time.time()
        
        try:
            response = requests.get(
                f"{self.base_url}/api/diary/calendar",
                params={"year": year, "month": month},
                headers={"Authorization": f"Bearer {self.token}"}
            )
            duration = time.time() - start
            
            if response.status_code == 200:
                data = response.json()
                
                # 验证响应结构
                if 'data' in data:
                    calendar_data = data['data']
                    
                    # 检查必需字段
                    required_fields = ['year', 'month', 'days', 'stats']
                    missing_fields = [f for f in required_fields if f not in calendar_data]
                    
                    if missing_fields:
                        self.log_test(
                            "日历接口 - 响应结构",
                            False,
                            f"缺少字段: {missing_fields}",
                            duration
                        )
                    else:
                        days_count = len(calendar_data['days'])
                        total_cards = calendar_data['stats']['total_this_month']
                        
                        self.log_test(
                            "日历接口 - 获取数据",
                            True,
                            f"找到 {days_count} 个有数据的日期, 本月共 {total_cards} 张卡片",
                            duration
                        )
                else:
                    self.log_test("日历接口", False, "响应缺少 data 字段", duration)
            else:
                self.log_test(
                    "日历接口",
                    False,
                    f"状态码: {response.status_code}",
                    duration
                )
                
        except Exception as e:
            self.log_test("日历接口", False, f"异常: {str(e)}", time.time() - start)
    
    def test_date_detail_api(self):
        """测试日期详情接口"""
        print("\n[3] 测试日期详情接口...")
        
        # 使用今天的日期
        today = datetime.now().date().isoformat()
        
        start = time.time()
        
        try:
            response = requests.get(
                f"{self.base_url}/api/diary/date",
                params={"date": today},
                headers={"Authorization": f"Bearer {self.token}"}
            )
            duration = time.time() - start
            
            if response.status_code == 200:
                data = response.json()
                
                if 'data' in data:
                    date_data = data['data']
                    cards_count = len(date_data.get('cards', []))
                    
                    self.log_test(
                        "日期详情接口",
                        True,
                        f"找到 {cards_count} 张卡片",
                        duration
                    )
                    
                    # 验证卡片结构
                    if cards_count > 0:
                        card = date_data['cards'][0]
                        required_card_fields = ['card_id', 'image_url', 'created_at', 'cocktail']
                        missing_fields = [f for f in required_card_fields if f not in card]
                        
                        if missing_fields:
                            self.log_test(
                                "日期详情接口 - 卡片结构",
                                False,
                                f"缺少字段: {missing_fields}",
                                0
                            )
                        else:
                            self.log_test(
                                "日期详情接口 - 卡片结构",
                                True,
                                "所有必需字段存在",
                                0
                            )
                else:
                    self.log_test("日期详情接口", False, "响应缺少 data 字段", duration)
            else:
                self.log_test(
                    "日期详情接口",
                    False,
                    f"状态码: {response.status_code}",
                    duration
                )
                
        except Exception as e:
            self.log_test("日期详情接口", False, f"异常: {str(e)}", time.time() - start)
    
    def test_stats_api(self):
        """测试统计接口"""
        print("\n[4] 测试统计接口...")
        
        start = time.time()
        
        try:
            response = requests.get(
                f"{self.base_url}/api/diary/stats",
                headers={"Authorization": f"Bearer {self.token}"}
            )
            duration = time.time() - start
            
            if response.status_code == 200:
                data = response.json()
                
                if 'data' in data:
                    stats = data['data']
                    
                    # 检查必需字段
                    required_fields = [
                        'total_cards', 'total_days', 'this_month',
                        'this_week', 'favorite_cocktails', 'first_card_date'
                    ]
                    missing_fields = [f for f in required_fields if f not in stats]
                    
                    if missing_fields:
                        self.log_test(
                            "统计接口 - 响应结构",
                            False,
                            f"缺少字段: {missing_fields}",
                            duration
                        )
                    else:
                        self.log_test(
                            "统计接口 - 获取数据",
                            True,
                            f"总卡片: {stats['total_cards']}, 总天数: {stats['total_days']}",
                            duration
                        )
                        
                        # 验证最爱鸡尾酒结构
                        if stats['favorite_cocktails']:
                            fav = stats['favorite_cocktails'][0]
                            if 'name_zh' in fav and 'count' in fav:
                                self.log_test(
                                    "统计接口 - 最爱鸡尾酒",
                                    True,
                                    f"Top 1: {fav['name_zh']} ({fav['count']}次)",
                                    0
                                )
                            else:
                                self.log_test(
                                    "统计接口 - 最爱鸡尾酒",
                                    False,
                                    "缺少必需字段",
                                    0
                                )
                else:
                    self.log_test("统计接口", False, "响应缺少 data 字段", duration)
            else:
                self.log_test(
                    "统计接口",
                    False,
                    f"状态码: {response.status_code}",
                    duration
                )
                
        except Exception as e:
            self.log_test("统计接口", False, f"异常: {str(e)}", time.time() - start)
    
    def test_performance(self):
        """性能测试"""
        print("\n[5] 测试性能...")
        
        now = datetime.now()
        year = now.year
        month = now.month
        
        # 测试 10 次请求的平均响应时间
        durations = []
        
        for i in range(10):
            start = time.time()
            try:
                response = requests.get(
                    f"{self.base_url}/api/diary/calendar",
                    params={"year": year, "month": month},
                    headers={"Authorization": f"Bearer {self.token}"},
                    timeout=5
                )
                if response.status_code == 200:
                    durations.append(time.time() - start)
            except:
                pass
        
        if durations:
            avg_duration = sum(durations) / len(durations)
            max_duration = max(durations)
            min_duration = min(durations)
            
            passed = avg_duration < 0.5  # 平均响应时间应小于 500ms
            
            self.log_test(
                "性能测试 - 日历接口",
                passed,
                f"平均: {avg_duration*1000:.2f}ms, 最小: {min_duration*1000:.2f}ms, 最大: {max_duration*1000:.2f}ms",
                avg_duration
            )
    
    def test_error_handling(self):
        """错误处理测试"""
        print("\n[6] 测试错误处理...")
        
        # 测试无效的月份参数
        start = time.time()
        try:
            response = requests.get(
                f"{self.base_url}/api/diary/calendar",
                params={"year": 2026, "month": 13},  # 无效月份
                headers={"Authorization": f"Bearer {self.token}"}
            )
            duration = time.time() - start
            
            if response.status_code == 422:
                self.log_test(
                    "错误处理 - 无效参数",
                    True,
                    "正确返回 422 错误",
                    duration
                )
            else:
                self.log_test(
                    "错误处理 - 无效参数",
                    False,
                    f"期望 422, 实际 {response.status_code}",
                    duration
                )
        except Exception as e:
            self.log_test("错误处理", False, f"异常: {str(e)}", time.time() - start)
        
        # 测试无效的日期格式
        start = time.time()
        try:
            response = requests.get(
                f"{self.base_url}/api/diary/date",
                params={"date": "invalid-date"},
                headers={"Authorization": f"Bearer {self.token}"}
            )
            duration = time.time() - start
            
            if response.status_code == 422:
                self.log_test(
                    "错误处理 - 无效日期",
                    True,
                    "正确返回 422 错误",
                    duration
                )
            else:
                self.log_test(
                    "错误处理 - 无效日期",
                    False,
                    f"期望 422, 实际 {response.status_code}",
                    duration
                )
        except Exception as e:
            self.log_test("错误处理", False, f"异常: {str(e)}", time.time() - start)
    
    def run_all_tests(self):
        """运行所有测试"""
        print("=" * 80)
        print("调酒日记功能 - API 测试")
        print("=" * 80)
        
        # 登录
        if not self.login():
            print("\n登录失败,无法继续测试")
            return
        
        # 运行所有测试
        self.test_calendar_api()
        self.test_date_detail_api()
        self.test_stats_api()
        self.test_performance()
        self.test_error_handling()
        
        # 统计结果
        print("\n" + "=" * 80)
        print("测试结果汇总")
        print("=" * 80)
        
        passed = sum(1 for r in self.test_results if "PASS" in r['status'])
        failed = sum(1 for r in self.test_results if "FAIL" in r['status'])
        total = len(self.test_results)
        
        print(f"\n总测试数: {total}")
        print(f"通过: {passed} ({passed/total*100:.1f}%)")
        print(f"失败: {failed} ({failed/total*100:.1f}%)")
        
        if failed == 0:
            print("\n🎉 所有测试通过!")
        else:
            print(f"\n⚠️  {failed} 个测试失败,请检查")
            print("\n失败的测试:")
            for result in self.test_results:
                if "FAIL" in result['status']:
                    print(f"  - {result['test']}: {result['message']}")


if __name__ == "__main__":
    tester = DiaryAPITester()
    tester.run_all_tests()
