# Google My Maps 动线图

这个目录存放从 `pages/plan-a-cn.html` 自动生成的 Google My Maps KML 文件。当前维护方式是：HTML 行程作为唯一源头，KML 从 HTML 重新生成，然后手动导入 Google My Maps。

## 文件说明

- `plan-a-cn-0523.kml`
- `plan-a-cn-0524.kml`
- `plan-a-cn-0525.kml`
- `plan-a-cn-0526.kml`
- `plan-a-cn-0527.kml`
- `plan-a-cn-0528.kml`
- `icons/`：KML 使用的数字图钉图标，按 `01.png`、`02.png` 这样的格式命名。
- `geocode-cache.json`：地点坐标缓存，避免每次都重新查询。
- `unresolved-locations.md`：无法自动定位的地点清单。当前如果没有未解析地点，会写明“当前没有未解析地点”。
- `generate_kml.py`：从 HTML 行程生成 KML 的脚本。

## My Maps 导入步骤

1. 打开 [Google My Maps](https://www.google.com/mymaps)。
2. 新建一张地图，例如命名为 `2026 Glasgow Plan A 中文版动线`。
3. 按日期顺序依次导入以下 KML 文件：
   - `plan-a-cn-0523.kml`
   - `plan-a-cn-0524.kml`
   - `plan-a-cn-0525.kml`
   - `plan-a-cn-0526.kml`
   - `plan-a-cn-0527.kml`
   - `plan-a-cn-0528.kml`
4. 将分享权限设置为 `Anyone with the link can view`。

导入后，My Maps 会把每个 KML 作为一个独立日期图层。KML 内部不会再按上午 / 下午 / 晚上拆分 Folder，避免超过 My Maps 的图层数量限制。建议图层顺序保持 `05/23` 到 `05/28`。

## 后续维护

如果只修改某一天的行程：

1. 修改 `pages/plan-a-cn.html` 里的对应行程。
2. 重新运行生成脚本。
3. 在 My Maps 中删除那一天的旧图层。
4. 导入新的那一天 KML。
5. 手动把该图层拖回日期顺序位置。

如果修改多天行程，建议重新导入全部 6 个 KML，避免旧图层残留。

## 重新生成

在仓库根目录运行：

```powershell
python maps\google-my-maps\generate_kml.py
```

如果只想使用已有坐标缓存、不联网查询新地点：

```powershell
python maps\google-my-maps\generate_kml.py --skip-geocode
```

坐标主要通过 Nominatim 查询并写入 `geocode-cache.json`。如果某个地点无法稳定解析，可以在 `generate_kml.py` 的 `LOCATION_OVERRIDES` 中补充更明确的查询词或手动坐标。

如果行程卡的 `location` 只是 `City Centre`、`West End` 这类区域提示，不要直接拿它做坐标。优先在 `generate_kml.py` 的 `ITEM_POINT_OVERRIDES` 中根据行程标题和备注指定真正要去的景点、车站或餐饮区域。

## 注意

- 点位名称格式为 `01｜上午｜地点名`。
- 地图 marker 使用数字图钉，编号按当天完整路线连续递增。
- 动线名称格式为 `05/24｜上午动线`。
- 上午、下午、晚上使用不同颜色。
- 每天只有一个 My Maps 图层；早中晚只是点位名称和动线颜色上的区分。
- KML 中的数字图钉引用 GitHub `stonfur` 分支里的 `icons/` 文件。导入 My Maps 前，建议先把本目录推送到 GitHub，确保图标 URL 可以公开访问。
- KML 中的线条是 My Maps 可显示的直线连接，不是 Google Maps 实时步行、公交或驾车路线。具体导航仍建议使用页面里的 Google Maps 分段链接。
