import os
import numpy as np
import pandas as pd
import geopandas as gpd
import rasterio
from rasterio.mask import mask
from PyQt5.QtWidgets import QHBoxLayout, QApplication  # 新增导入
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QGridLayout, QLabel, QLineEdit,
                             QPushButton, QFileDialog, QMessageBox, QProgressDialog,
                             QCheckBox, QGroupBox, QScrollArea, QApplication)  # 确保QApplicatio
from PyQt5.QtCore import Qt
import traceback
from rasterio.warp import calculate_default_transform, reproject, Resampling
from rasterio.crs import CRS

class SingleBandIndexTab(QWidget):
    def __init__(self):
        super().__init__()
        # 波段中文映射表
        self.band_names = {
            'Red': '红色',
            'Green': '绿色',
            'Blue': '蓝色',
            'RedEdge': '红边',
            'NIR': '近红外'
        }
        
        # 植被指数定义
        self.vegetation_indices = {
            'NDVI': {
                'bands': ['NIR', 'Red'], 
                'formula': lambda NIR, Red: (NIR - Red) / (NIR + Red + 1e-10),
                'name': '归一化差异植被指数'
            },
            'EVI': {
                'bands': ['NIR', 'Red', 'Blue'],
                'formula': lambda NIR, Red, Blue: 2.5*(NIR - Red)/(NIR + 6*Red - 7.5*Blue + 1),
                'name': '增强型植被指数'
            },
            'SAVI': {
                'bands': ['NIR', 'Red'],
                'formula': lambda NIR, Red: (NIR - Red)/(NIR + Red + 0.5)*(1 + 0.5),
                'name': '土壤调节植被指数'
            },
            'OSAVI': {
                'bands': ['NIR', 'Red'],
                'formula': lambda NIR, Red: (NIR - Red)/(NIR + Red + 0.16),
                'name': '优化型土壤调节植被指数'
            },
            'NDRE': {
                'bands': ['NIR', 'RedEdge'],
                'formula': lambda NIR, RedEdge: (NIR - RedEdge)/(NIR + RedEdge + 1e-10),
                'name': '归一化红边指数'
            },
            'GNDVI': {
                'bands': ['NIR', 'Green'],
                'formula': lambda NIR, Green: (NIR - Green)/(NIR + Green + 1e-10),
                'name': '绿光归一化差异植被指数'
            },
            'ARVI': {
                'bands': ['NIR', 'Red', 'Blue'],
                'formula': lambda NIR, Red, Blue: (NIR - (2*Red - Blue))/(NIR + (2*Red - Blue) + 1e-10),
                'name': '大气阻抗植被指数'
            },
            'LCI': {
                'bands': ['NIR', 'RedEdge', 'Green'],
                'formula': lambda NIR, RedEdge, Green: (NIR - RedEdge)/(NIR + Green + 1e-10),
                'name': '叶绿素指数'
            },
            'RVI': {
                'bands': ['NIR', 'Red'],
                'formula': lambda NIR, Red: NIR / (Red + 1e-10),
                'name': '比值植被指数'
            },
            'DVI': {
                'bands': ['NIR', 'Red'],
                'formula': lambda NIR, Red: NIR - Red,
                'name': '差值植被指数'
            },
            'RDVI': {
                'bands': ['NIR', 'Red'],
                'formula': lambda NIR, Red: (NIR - Red)/np.sqrt(NIR + Red + 1e-10),
                'name': '重归一化差异植被指数'
            },
            'CIRE': {
                'bands': ['RedEdge', 'Red'],
                'formula': lambda RedEdge, Red: (RedEdge/Red) - 1,
                'name': '红边叶绿素指数'
            },
        }
        self.init_ui()
        self.band_files = {}

    def init_ui(self):
        """初始化界面布局"""
        main_layout = QVBoxLayout()

        # === 输入参数部分 ===
        input_grid = QGridLayout()
        current_row = 0

        # 单波段输入（按中文顺序排列）
        bands_order = ['Red', 'Green', 'Blue', 'RedEdge', 'NIR']
        self.band_widgets = {}
        for band in bands_order:
            chinese_name = self.band_names[band]
            label = QLabel(f"{chinese_name}波段（{band}）:")
            edit = QLineEdit()
            btn = QPushButton("浏览")
            btn.clicked.connect(lambda _, e=edit: self.browse_file(e, "TIFF文件", "TIFF (*.tif)"))
            
            input_grid.addWidget(label, current_row, 0)
            input_grid.addWidget(edit, current_row, 1)
            input_grid.addWidget(btn, current_row, 2)
            self.band_widgets[band] = edit
            current_row += 1

        # 矢量文件输入
        self.shp_label = QLabel("矢量边界文件（shp）:")
        self.shp_edit = QLineEdit()
        self.shp_btn = QPushButton("浏览")
        self.shp_btn.clicked.connect(lambda: self.browse_file(self.shp_edit, "矢量文件", "Shapefile (*.shp)"))
        input_grid.addWidget(self.shp_label, current_row, 0)
        input_grid.addWidget(self.shp_edit, current_row, 1)
        input_grid.addWidget(self.shp_btn, current_row, 2)
        current_row += 1

        main_layout.addLayout(input_grid)

        # === 植被指数选择 ===
        index_header = QLabel("内置植被指数计算选项（可多选）")
        index_header.setStyleSheet("font-weight: bold; font-size: 12pt; margin-bottom: 8px;")
        main_layout.addWidget(index_header)

        index_group = QGroupBox()
        index_group.setStyleSheet("QGroupBox{border:1px solid #D0D0D0; border-radius:3px;}")
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        
        grid_layout = QGridLayout()
        grid_layout.setContentsMargins(3, 3, 3, 3)
        
        cols = 3
        row, col = 0, 0
        
        sorted_indices = sorted(self.vegetation_indices.keys(), key=lambda x: self.vegetation_indices[x]['name'])
        
        self.checkboxes = {}
        for idx in sorted_indices:
            display_name = f"{self.vegetation_indices[idx]['name']}（{idx}）"
            cb = QCheckBox(display_name)
            cb.setStyleSheet("QCheckBox{margin-right: 15px;}")
            cb.setToolTip(f"计算公式：\n{self.get_formula_text(idx)}")
            grid_layout.addWidget(cb, row, col)
            self.checkboxes[idx] = cb
            
            col += 1
            if col >= cols:
                col = 0
                row += 1
        
        index_group.setLayout(grid_layout)
        scroll.setWidget(index_group)
        scroll.setMinimumHeight(130)
        main_layout.addWidget(scroll)

        # === 输出设置 === (新增位置)
        output_group = QGroupBox("输出设置")
        output_layout = QHBoxLayout()
        self.output_label = QLabel("输出文件夹:")
        self.output_edit = QLineEdit()
        self.output_btn = QPushButton("浏览")
        self.output_btn.clicked.connect(self.select_output_folder)
        output_layout.addWidget(self.output_label)
        output_layout.addWidget(self.output_edit)
        output_layout.addWidget(self.output_btn)
        output_group.setLayout(output_layout)
        main_layout.addWidget(output_group)

        # === 计算按钮 ===
        self.run_btn = QPushButton("▶ 开始计算选定植被指数")
        self.run_btn.setStyleSheet(
            "QPushButton{font-size:12pt; padding:8px; background:#4CAF50; color:white;}"
            "QPushButton:hover{background:#45a049;}"
        )
        self.run_btn.clicked.connect(self.process_data)
        main_layout.addWidget(self.run_btn)

        self.setLayout(main_layout)

    def select_output_folder(self):
            """选择输出文件夹"""
            folder = QFileDialog.getExistingDirectory(self, "选择输出文件夹", "")
            if folder:
                self.output_edit.setText(folder)


    def browse_file(self, edit_widget, title, filter):
        """通用文件浏览"""
        filename, _ = QFileDialog.getOpenFileName(self, title, "", filter)
        if filename:
            edit_widget.setText(filename)

    def validate_inputs(self):
        """修改后的输入验证"""
        errors = []
        
        # 检查输出文件夹
        output_folder = self.output_edit.text().strip()
        if not output_folder:
            errors.append("必须指定输出文件夹")
        else:
            try:
                os.makedirs(output_folder, exist_ok=True)
                if not os.access(output_folder, os.W_OK):
                    errors.append("输出文件夹没有写入权限")
            except Exception as e:
                errors.append(f"无法创建输出文件夹：{str(e)}")

        # 检查矢量文件
        if not self.shp_edit.text().endswith('.shp'):
            errors.append("矢量文件格式错误，请选择.shp文件")
        elif not os.path.exists(self.shp_edit.text()):
            errors.append("矢量文件路径不存在")

        # 检查波段文件
        required_bands = set()
        for idx_name, cb in self.checkboxes.items():
            if cb.isChecked():
                required_bands.update(self.vegetation_indices[idx_name]['bands'])
        
        for band in required_bands:
            widget = self.band_widgets[band]
            path = widget.text()
            if not path:
                errors.append(f"需要 {self.band_names[band]} 波段文件")
            elif not path.endswith('.tif'):
                errors.append(f"{self.band_names[band]}波段：文件格式应为TIFF")
            elif not os.path.exists(path):
                errors.append(f"{self.band_names[band]}波段：文件路径不存在")

        if errors:
            QMessageBox.critical(self, "输入验证错误", "发现以下问题：\n\n• " + "\n• ".join(errors))
            return False
        return True


    def process_data(self):
        """修改后的主处理流程 - 完整实现"""
        try:
            # === 输入验证 ===
            if not self.validate_inputs():
                return

            # === 准备基础数据 ===
            output_folder = self.output_edit.text().strip()
            selected_indices = [idx for idx, cb in self.checkboxes.items() if cb.isChecked()]
            total_indices = len(selected_indices)
            
            if total_indices == 0:
                QMessageBox.warning(self, "警告", "请至少选择一个植被指数")
                return

            # 读取矢量数据（只读一次）
            try:
                gdf = gpd.read_file(self.shp_edit.text())
            except Exception as e:
                QMessageBox.critical(self, "矢量文件错误", f"无法读取矢量文件：\n{str(e)}")
                return

            # === 初始化进度条 ===
            progress = QProgressDialog(
                "处理进度", 
                "取消", 
                0, 
                total_indices, 
                self
            )
            progress.setWindowTitle("植被指数计算进度")
            progress.setWindowModality(Qt.WindowModal)
            progress.setMinimumWidth(450)
            progress.setMinimumDuration(0)

            success_count = 0
            failed_indices = []

            # === 处理每个植被指数 ===
            for index_num, idx_name in enumerate(selected_indices, 1):
                if progress.wasCanceled():
                    break

                # 更新进度显示
                progress.setValue(index_num)
                progress_label = (
                    f"正在处理 ({index_num}/{total_indices})\n"
                    f"当前指数：{self.vegetation_indices[idx_name]['name']} ({idx_name})\n"
                    f"输出目录：{os.path.basename(output_folder)}"
                )
                progress.setLabelText(progress_label)

                # 生成文件路径
                tif_filename = f"{idx_name}.tif"
                csv_filename = f"{idx_name}_统计结果.csv"
                tif_path = os.path.join(output_folder, tif_filename)
                csv_path = os.path.join(output_folder, csv_filename)

                try:
                    # === 生成指数影像 ===
                    self.generate_index(idx_name, tif_path)
                    
                    # === 计算统计数据 ===
                    self.calculate_statistics(tif_path, gdf, csv_path)
                    
                    success_count += 1

                except rasterio.errors.RasterioIOError as e:
                    error_msg = f"文件写入失败：{str(e)}"
                    failed_indices.append(f"{idx_name} (IO错误)")
                    print(f"Error writing {idx_name}: {traceback.format_exc()}")

                except ValueError as e:
                    error_msg = f"计算错误：{str(e)}"
                    failed_indices.append(f"{idx_name} (计算错误)")
                    print(f"Calculation error {idx_name}: {traceback.format_exc()}")

                except Exception as e:
                    error_msg = f"未知错误：{str(e)}"
                    failed_indices.append(f"{idx_name} (未知错误)")
                    print(f"Unexpected error {idx_name}: {traceback.format_exc()}")

                else:  # 如果成功
                    print(f"Successfully processed {idx_name}")
                    
                finally:  # 确保界面更新
                    QApplication.processEvents()

            # === 关闭进度条 ===
            progress.close()

            # === 生成结果报告 ===
            report_lines = [
                f"处理完成！共处理 {total_indices} 个指数",
                f"✓ 成功：{success_count}",
                f"✗ 失败：{len(failed_indices)}",
                f"输出目录：{output_folder}"
            ]
            
            if failed_indices:
                report_lines.extend([
                    "\n失败详情：",
                    "----------------------------",
                    *failed_indices
                ])

            # 显示最终报告
            report_msg = QMessageBox()
            report_msg.setWindowTitle("处理结果")
            report_msg.setIcon(QMessageBox.Information)
            report_msg.setText("\n".join(report_lines))
            report_msg.setStandardButtons(QMessageBox.Ok)
            report_msg.exec_()

        except Exception as e:
            QMessageBox.critical(
                self, 
                "致命错误", 
                f"程序遇到未处理的异常：\n{str(e)}\n\n"
                f"跟踪信息：\n{traceback.format_exc()}"
            )
    
            
    def process_multiple_data(self):
        """处理多张植被指数影像（优化版本）"""
        files_text = self.multi_precomp_edit.toPlainText().strip()
        if not self.validate_inputs('multi'):
            return
        
        files = [f.strip() for f in files_text.split(";\n") if f.strip()]
        total_files = len(files)
        success_count = 0
        total_errors = 0

        # 显示批量处理进度
        progress = QProgressDialog(
            "批量处理进度", 
            "取消", 
            0, 
            total_files, 
            self
        )
        progress.setWindowTitle("批量处理中...")
        progress.setWindowModality(Qt.WindowModal)

        for i, file in enumerate(files, 1):
            if progress.wasCanceled():
                break
            
            progress.setValue(i)
            progress.setLabelText(f"正在处理文件 {i}/{total_files}\n{os.path.basename(file)}")
            
            try:
                error_count = self.process_data(file)
                if error_count == 0:
                    success_count += 1
                total_errors += error_count
            except:
                total_errors += 1

        progress.close()
        
        # 显示汇总报告
        report = f"处理完成！\n成功文件数: {success_count}/{total_files}"
        if total_errors > 0:
            report += f"\n总错误区域数: {total_errors}"
        QMessageBox.information(self, "批量处理报告", report)

    def get_formula_text(self, index_name):
        """生成公式说明文本"""
        formulas = {
            'NDVI': "(近红外 - 红波段) / (近红外 + 红波段)",
            'EVI': "2.5 × (近红外 - 红波段) / (近红外 + 6 × 红波段 - 7.5 × 蓝波段 + 1)",
            'SAVI': "(近红外 - 红波段) / (近红外 + 红波段 + 0.5) × 1.5",
            'OSAVI': "(近红外 - 红波段) / (近红外 + 红波段 + 0.16)",
            'NDRE': "(近红外 - 红边波段) / (近红外 + 红边波段)",
            'GNDVI': "(近红外 - 绿波段) / (近红外 + 绿波段)",
            'ARVI': "[近红外 - (2 × 红波段 - 蓝波段)] / [近红外 + (2 × 红波段 - 蓝波段)]",
            'LCI': "(近红外 - 红边波段) / (近红外 + 绿波段)",
            'RVI': "近红外 / 红波段",
            'DVI': "近红外 - 红波段",
            'RDVI': "(近红外 - 红波段) / √(近红外 + 红波段)",
            'CIRE': "(红边波段 / 红波段) - 1",
        }
        return formulas.get(index_name, "自定义计算公式") 
        
    def resample_to_base(self, data, src_transform, dst_transform, dst_width, dst_height):
        """将数据重采样到基准空间分辨率"""
        from rasterio.enums import Resampling
        
        resampled = np.zeros((dst_height, dst_width), dtype=data.dtype)
        
        reproject(
            source=data,
            destination=resampled,
            src_transform=src_transform,
            src_crs=CRS.from_epsg(4326),  # 假设源坐标系已知
            dst_transform=dst_transform,
            dst_crs=CRS.from_epsg(4326),   # 目标坐标系应与基准一致
            resampling=Resampling.bilinear
        )
        
        return resampled
    
        
    def generate_index(self, index_name, output_path):
        """生成植被指数影像（含动态坐标转换与重采样）"""
        try:
            idx_config = self.vegetation_indices[index_name]
            bands = idx_config['bands']
            formula = idx_config['formula']

            # =======================================================================
            # 步骤1：确定基准坐标系（以首个输入波段为基准）
            # =======================================================================
            base_band = bands[0]
            base_path = self.band_widgets[base_band].text()
            
            with rasterio.open(base_path) as base_src:
                target_crs = base_src.crs  # 基准坐标系
                target_transform = base_src.transform
                target_width = base_src.width
                target_height = base_src.height
                profile = base_src.profile.copy()

            # =======================================================================
            # 步骤2：读取并对齐所有波段数据到基准坐标系
            # =======================================================================
            aligned_bands = {}
            for band in bands:
                band_path = self.band_widgets[band].text()
                
                with rasterio.open(band_path) as src:
                    # 情况1：坐标系与基准一致
                    if src.crs == target_crs:
                        data = src.read(1).astype('float32')
                    
                    # 情况2：需要执行坐标转换
                    else:
                        # 计算目标坐标系下的变换参数
                        transform, width, height = calculate_default_transform(
                            src.crs, target_crs,
                            src.width, src.height,
                            *src.bounds
                        )
                        
                        # 初始化目标数组
                        data = np.zeros((height, width), dtype=np.float32)
                        
                        # 执行重投影与重采样
                        reproject(
                            source=src.read(1),
                            destination=data,
                            src_transform=src.transform,
                            src_crs=src.crs,
                            dst_transform=transform,
                            dst_crs=target_crs,
                            resampling=Resampling.bilinear  # 双线性插值
                        )
                        
                        # 二次重采样到基准分辨率（确保所有波段空间对齐）
                        data = self.resample_to_base(
                            data, transform, 
                            target_transform, 
                            target_width, target_height
                        )
                    
                    aligned_bands[band] = data

            # =======================================================================
            # 步骤3：应用植被指数计算公式
            # =======================================================================
            result = formula(**aligned_bands)
            
            # 处理异常值
            result = np.where(np.isinf(result), np.nan, result)
            result = np.where(np.isneginf(result), np.nan, result)

            # =======================================================================
            # 步骤4：保存结果影像
            # =======================================================================
            profile.update({
                'driver': 'GTiff',
                'height': target_height,
                'width': target_width,
                'transform': target_transform,
                'crs': target_crs,
                'dtype': 'float32',
                'nodata': np.nan,
                'count': 1,
                'compress': 'lzw'  # 启用LZW压缩
            })
            
            with rasterio.open(output_path, 'w', **profile) as dst:
                dst.write(result, 1)
                
            return True

        except rasterio.errors.RasterioError as e:
            print(f"栅格操作错误: {str(e)}")
            raise
        except ValueError as e:
            print(f"数值计算错误: {str(e)}")
            raise
        except Exception as e:
            print(f"生成指数{index_name}时发生未知错误: {str(e)}")
            raise

    def calculate_statistics(self, raster_path, gdf, csv_path):
        """计算统计结果"""
        # 读取矢量数据
        gdf = gdf.to_crs(rasterio.open(raster_path).crs)
        all_stats = []

        with rasterio.open(raster_path) as src:
            for _, row in gdf.iterrows():
                geom = row.geometry
                zone_id = row.get('name', '未命名区域')

                try:
                    # 对每个区域进行掩膜处理
                    masked, _ = mask(src, [geom], crop=True, nodata=src.nodata)
                    data = masked[0].astype('float32')
                    valid_data = data[~np.isnan(data)]  # 去除NaN值

                    # 如果有有效数据，计算统计量
                    if valid_data.size > 0:
                        stats = {
                            '区域名称': zone_id,
                            '最小值': np.nanmin(valid_data),  # 最小值
                            '最大值': np.nanmax(valid_data),  # 最大值
                            '平均值': np.nanmean(valid_data),  # 平均值
                            '中位数': np.nanmedian(valid_data),  # 中位数
                            '标准差': np.nanstd(valid_data),  # 标准差
                            '有效像元数': valid_data.size,  # 有效像元数
                            '总像元数': data.size  # 总像元数
                        }
                        all_stats.append(stats)
                    else:
                        # 如果没有有效数据，统计量设置为NaN
                        stats = {
                            '区域名称': zone_id,
                            '最小值': np.nan,
                            '最大值': np.nan,
                            '平均值': np.nan,
                            '中位数': np.nan,
                            '标准差': np.nan,
                            '有效像元数': 0,
                            '总像元数': data.size
                        }
                        all_stats.append(stats)
                except Exception as e:
                    print(f"区域 {zone_id} 统计失败: {str(e)}")
                    continue

        # 保存CSV
        if all_stats:
            df = pd.DataFrame(all_stats)
            df.to_csv(csv_path, index=False, encoding='utf_8_sig', float_format="%.4f")


