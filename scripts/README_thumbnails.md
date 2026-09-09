# 缩略图功能使用说明

## 快速验证

运行验证脚本检查缩略图功能是否正常：

```bash
python scripts/verify_thumbnails.py
```

## 目录结构

```
app/static/cocktail/
├── images/          # 原图目录（已存在）
│   └── 57_cuba_libre.jpg
└── thumbnails/      # 缩略图目录（自动创建）
    └── 57_cuba_libre_thumb100_629940db.jpg
```

## API 使用

### 请求

```bash
GET /api/map/themes/<theme_id>
Authorization: Bearer <token>
```

### 响应

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "theme": {
      "id": 17,
      "name_zh": "深夜优雅",
      "preview_url": "http://domain/static/cocktail/thumbnails/theme_17_thumb100.jpg"
    },
    "nodes": [
      {
        "id": 397,
        "display_name_zh": "干马天尼",
        "image_url": "http://domain/static/cocktail/images/82_dry_martini.jpg",
        "thumbnail_url": "http://domain/static/cocktail/thumbnails/82_dry_martini_thumb100_a1d41037.jpg"
      }
    ]
  }
}
```

## 工作原理

1. **首次请求**：检测到缩略图不存在时自动生成
2. **后续请求**：直接返回已缓存的缩略图 URL
3. **文件命名**：使用原图路径 + 尺寸的 MD5 hash，确保唯一性

## 配置参数

在 `app/utils/image_utils.py` 中可调整：

- `size`: 缩略图宽度（默认 100px）
- `quality`: JPEG 质量（默认 85）

## 性能数据

- **压缩比**：约 200x
- **原图**：~750KB
- **缩略图**：~3.5KB
- **生成时间**：<100ms/图

## 故障排查

### 缩略图未生成

1. 检查目录权限：
   ```bash
   ls -la app/static/cocktail/thumbnails/
   ```

2. 检查原图是否存在：
   ```bash
   ls -la app/static/cocktail/images/
   ```

3. 查看应用日志：
   ```bash
   tail -f logs/app.log | grep thumbnail
   ```

### 重新生成所有缩略图

```bash
# 删除现有缩略图
rm -rf app/static/cocktail/thumbnails/*.jpg

# 重启应用，下次请求时会自动重新生成
```

## 批量预生成（可选）

如需在部署时预生成所有缩略图：

```python
from app import create_app
from app.utils.image_utils import generate_thumbnail
from sqlalchemy import text
from app.extensions import db
import os

app = create_app()
with app.app_context():
    # 获取所有鸡尾酒图片
    cocktails = db.session.execute(
        text("SELECT id, image_url FROM cocktails WHERE image_url IS NOT NULL")
    ).fetchall()
    
    print(f"预生成 {len(cocktails)} 个缩略图...")
    
    for c in cocktails:
        thumbnail = generate_thumbnail(c.image_url, size=100)
        if thumbnail:
            print(f"✓ {c.id}: {thumbnail}")
        else:
            print(f"✗ {c.id}: 生成失败")
    
    print("完成！")
```

## 监控指标

建议监控以下指标：

- 缩略图目录大小
- 缩略图生成失败率
- 平均生成时间
- 缓存命中率

## 清理策略

缩略图会持久保存，如需清理：

```bash
# 清理超过 30 天未访问的缩略图
find app/static/cocktail/thumbnails/ -name "*.jpg" -atime +30 -delete
```

## 扩展建议

### 多尺寸支持

修改 `generate_thumbnail` 调用时传入不同的 `size` 参数：

```python
# 生成不同尺寸
thumbnail_50 = get_or_generate_thumbnail(image_url, size=50)
thumbnail_100 = get_or_generate_thumbnail(image_url, size=100)
thumbnail_200 = get_or_generate_thumbnail(image_url, size=200)
```

### WebP 格式

在 `image_utils.py` 中添加 WebP 支持：

```python
# 保存为 WebP
img_resized.save(thumb_path, 'WEBP', quality=quality, optimize=True)
```

### CDN 集成

将生成的缩略图上传到 CDN：

```python
# 在 generate_thumbnail 函数中添加
# 生成缩略图后上传到 CDN
cdn_url = upload_to_cdn(thumb_path)
return cdn_url
```
