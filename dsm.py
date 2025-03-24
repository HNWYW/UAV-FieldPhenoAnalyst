import numpy as np
import matplotlib.pyplot as plt
from matplotlib import cm
from mpl_toolkits.mplot3d import Axes3D
import rasterio

# 1. 读取DSM数据
with rasterio.open(r'dsm_file/22_zaodaoyunsui_dsm.tif') as src:
    dsm = src.read(1)
    transform = src.transform

# 2. 创建坐标网格
xres, yres = transform[0], transform[4]
x = np.arange(0, dsm.shape[1]*xres, xres)
y = np.arange(0, dsm.shape[0]*yres, yres)
x, y = np.meshgrid(x, y)

# 3. 数据预处理
dsm = np.ma.masked_where(dsm < 0, dsm)  # 过滤负值
dsm = np.ma.masked_invalid(dsm)         # 过滤NaN值

# 4. 创建三维图形
fig = plt.figure(figsize=(16, 12))
ax = fig.add_subplot(111, projection='3d')

# 5. 设置可视化参数
surf = ax.plot_surface(
    x, y, dsm,
    cmap=cm.viridis,          # 使用Viridis颜色映射
    rstride=2, cstride=2,     # 降低采样率提升渲染速度
    linewidth=0,
    antialiased=True,
    edgecolor='none',         # 移除网格线
    shade=True,               # 启用阴影
    alpha=0.95               # 设置透明度
)

# 6. 添加颜色条
cbar = fig.colorbar(surf, shrink=0.6, aspect=20)
cbar.set_label('Canopy Height (m)', fontsize=12)

# 7. 设置光照和视角
ax.view_init(elev=45, azim=315)  # 设置视角角度
ax.set_axis_off()               # 关闭坐标轴

# 8. 添加光照效果（增强三维感）
surf.set_facecolor((0,0,0,0))  # 透明表面
light = plt.LightSource(azdeg=315, altdeg=45)
illuminated_surface = light.shade(
    dsm,
    cmap=cm.viridis,
    blend_mode='soft',
    vert_exag=0.5,            # 垂直 exaggeration
    dx=xres, dy=yres
)
ax.plot_surface(x, y, dsm, facecolors=illuminated_surface, rstride=1, cstride=1)

# 9. 保存高清图像
plt.savefig('3d_canopy.png', dpi=300, bbox_inches='tight', transparent=True)
plt.show()