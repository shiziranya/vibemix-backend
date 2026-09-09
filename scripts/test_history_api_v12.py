#!/usr/bin/env python3
"""
测试推荐历史接口 v1.2 格式

验证点：
1. ingredients 在顶层（与 cocktail 同级）
2. ingredients 包含 status 和 substitute 字段
3. ai 对象包含 mood_caption 字段
4. cocktail 对象不包含 ingredients
"""
import json
import sys


def validate_history_item(item: dict, index: int) -> list[str]:
    """验证单个历史记录项的格式"""
    errors = []
    prefix = f"items[{index}]"
    
    # 1. 检查顶层必需字段
    required_fields = ["id", "session_id", "created_at", "cocktail", "ingredients", "input", "ai"]
    for field in required_fields:
        if field not in item:
            errors.append(f"{prefix}.{field} 缺失")
    
    # 2. 检查 cocktail 对象
    if "cocktail" in item:
        cocktail = item["cocktail"]
        if "ingredients" in cocktail:
            errors.append(f"{prefix}.cocktail 不应该包含 ingredients 字段")
        
        # cocktail 应该包含这些字段
        cocktail_fields = ["id", "name", "name_zh", "abv_level", "difficulty"]
        for field in cocktail_fields:
            if field not in cocktail:
                errors.append(f"{prefix}.cocktail.{field} 缺失")
    
    # 3. 检查 ingredients 数组（顶层）
    if "ingredients" in item:
        if not isinstance(item["ingredients"], list):
            errors.append(f"{prefix}.ingredients 应该是数组")
        else:
            for i, ing in enumerate(item["ingredients"]):
                # 检查必需字段
                ing_required = ["id", "name", "name_zh", "status", "substitute"]
                for field in ing_required:
                    if field not in ing:
                        errors.append(f"{prefix}.ingredients[{i}].{field} 缺失")
                
                # 检查 status 的值
                if "status" in ing:
                    valid_status = ["owned", "missing", "available"]
                    if ing["status"] not in valid_status:
                        errors.append(
                            f"{prefix}.ingredients[{i}].status 值无效: {ing['status']} "
                            f"(应该是 {valid_status} 之一)"
                        )
                
                # 检查 substitute 类型
                if "substitute" in ing:
                    if ing["substitute"] is not None and not isinstance(ing["substitute"], str):
                        errors.append(
                            f"{prefix}.ingredients[{i}].substitute 应该是 string 或 null"
                        )
    
    # 4. 检查 ai 对象
    if "ai" in item:
        ai = item["ai"]
        ai_fields = ["reason", "poetic_copy", "mood_caption"]
        for field in ai_fields:
            if field not in ai:
                errors.append(f"{prefix}.ai.{field} 缺失")
    
    # 5. 检查 input 对象
    if "input" in item:
        input_obj = item["input"]
        input_fields = ["mood_tags", "flavor_tags", "recipe_type"]
        for field in input_fields:
            if field not in input_obj:
                errors.append(f"{prefix}.input.{field} 缺失")
    
    return errors


def main():
    """读取 stdin 的 JSON 响应并验证格式"""
    try:
        # 从标准输入读取 JSON
        data = json.load(sys.stdin)
        
        # 检查顶层结构
        if "code" not in data:
            print("❌ 缺少 code 字段")
            return 1
        
        if data["code"] != 0:
            print(f"❌ API 返回错误: code={data['code']}, message={data.get('message')}")
            return 1
        
        if "data" not in data:
            print("❌ 缺少 data 字段")
            return 1
        
        response_data = data["data"]
        
        # 检查分页字段
        pagination_fields = ["items", "total", "page", "per_page", "total_pages"]
        for field in pagination_fields:
            if field not in response_data:
                print(f"❌ data.{field} 缺失")
                return 1
        
        items = response_data["items"]
        if not isinstance(items, list):
            print("❌ data.items 应该是数组")
            return 1
        
        if len(items) == 0:
            print("⚠️  警告: 历史记录为空，无法验证格式")
            return 0
        
        # 验证每个历史记录项
        all_errors = []
        for i, item in enumerate(items):
            errors = validate_history_item(item, i)
            all_errors.extend(errors)
        
        # 输出结果
        if all_errors:
            print(f"❌ 发现 {len(all_errors)} 个格式错误:\n")
            for error in all_errors:
                print(f"  - {error}")
            return 1
        else:
            print(f"✅ 验证通过！共检查 {len(items)} 条历史记录")
            print(f"\n格式检查项:")
            print(f"  ✓ ingredients 在顶层")
            print(f"  ✓ ingredients 包含 status 和 substitute")
            print(f"  ✓ ai 对象包含 mood_caption")
            print(f"  ✓ cocktail 对象不包含 ingredients")
            
            # 显示示例数据
            if len(items) > 0:
                first_item = items[0]
                print(f"\n示例数据 (第一条记录):")
                print(f"  - Cocktail: {first_item['cocktail'].get('name_zh', 'N/A')}")
                print(f"  - Ingredients 数量: {len(first_item.get('ingredients', []))}")
                print(f"  - Mood Caption: {first_item['ai'].get('mood_caption', 'N/A')}")
                
                # 显示原料状态统计
                if first_item.get('ingredients'):
                    status_count = {}
                    substitute_count = 0
                    for ing in first_item['ingredients']:
                        status = ing.get('status', 'unknown')
                        status_count[status] = status_count.get(status, 0) + 1
                        if ing.get('substitute'):
                            substitute_count += 1
                    
                    print(f"  - 原料状态: {dict(status_count)}")
                    print(f"  - 有替代建议: {substitute_count} 个")
            
            return 0
    
    except json.JSONDecodeError as e:
        print(f"❌ JSON 解析错误: {e}")
        return 1
    except Exception as e:
        print(f"❌ 验证失败: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
