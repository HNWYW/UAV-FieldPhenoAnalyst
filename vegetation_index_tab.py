import os
import pandas as pd
import numpy as np
import geopandas as gpd
import rasterio
from rasterio.mask import mask
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QGridLayout, QLabel, QLineEdit,
                             QTextEdit, QPushButton, QFileDialog, QMessageBox, QProgressDialog,QApplication,QSizePolicy)
from PyQt5.QtCore import Qt
import traceback
from datetime import datetime
# 新增导入
from PyQt5.QtWidgets import QHBoxLayout, QGroupBox

class VegetationIndexTab(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()
        # 状态变量集中初始化
        self.gdf = None  # 存储转换后的矢量数据
        self.coordinate_conversion_choice = None  # 批量处理转换选择
        self.coordinate_system_checked = False  # 单文件检查标记

    def init_ui(self):
        """初始化界面布局"""
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(15)

        # === 输入参数部分 ===
        input_grid = QGridLayout()
        current_row = 0

        # 矢量文件输入（保持不变）
        self.shp_label = QLabel("矢量文件 (shp):")
        self.shp_edit = QLineEdit()
        self.shp_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.shp_browse_btn = QPushButton("浏览")
        self.shp_browse_btn.clicked.connect(lambda: self.browse_file(self.shp_edit, "矢量文件", "Shapefile (*.shp)"))
        input_grid.addWidget(self.shp_label, current_row, 0)
        input_grid.addWidget(self.shp_edit, current_row, 1)
        input_grid.addWidget(self.shp_browse_btn, current_row, 2)
        current_row += 1

        # 单张影像输入（保持不变）
        self.single_precomp_label = QLabel("单张植被指数影像:")
        self.single_precomp_edit = QLineEdit()
        self.single_precomp_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.single_precomp_btn = QPushButton("浏览")
        self.single_precomp_btn.clicked.connect(lambda: self.browse_file(self.single_precomp_edit, "单张植被指数影像", "TIFF (*.tif)"))
        input_grid.addWidget(self.single_precomp_label, current_row, 0)
        input_grid.addWidget(self.single_precomp_edit, current_row, 1)
        input_grid.addWidget(self.single_precomp_btn, current_row, 2)
        current_row += 1

        # === 修改的多张影像输入部分 ===
        self.multi_precomp_label = QLabel("多张植被指数影像 (多个路径用分号隔开):")
        self.multi_precomp_edit = QTextEdit()
        self.multi_precomp_edit.setPlaceholderText("每个路径后按回车添加\n路径之间使用分号分隔")
        self.multi_precomp_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.multi_precomp_btn = QPushButton("浏览")
        self.multi_precomp_btn.clicked.connect(self.browse_multiple_files)
        
        # 新的水平布局
        hbox = QHBoxLayout()
        hbox.addWidget(self.multi_precomp_edit, 4)  # 文本框占4份宽度
        hbox.addWidget(self.multi_precomp_btn, 1)   # 按钮占1份宽度
        hbox.setContentsMargins(0, 0, 0, 0)
        
        input_grid.addWidget(self.multi_precomp_label, current_row, 0)
        input_grid.addLayout(hbox, current_row, 1, 1, 2)  # 占据1行2列
        current_row += 1

        # === 后续保持不变 ===
        main_layout.addLayout(input_grid)
        
        # 输出设置部分（保持不变）
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

        # 按钮部分（保持不变）
        self.single_run_btn = QPushButton("▶ 计算单张预合成植被指数")
        self.single_run_btn.setStyleSheet("QPushButton{font-size:12pt; padding:8px; background:#4CAF50; color:white;} QPushButton:hover{background:#45a049;}")
        self.single_run_btn.clicked.connect(self.process_single_data)
        main_layout.addWidget(self.single_run_btn)

        self.multi_run_btn = QPushButton("▶ 计算多张预合成植被指数")
        self.multi_run_btn.setStyleSheet("QPushButton{font-size:12pt; padding:8px; background:#4CAF50; color:white;} QPushButton:hover{background:#45a049;}")
        self.multi_run_btn.clicked.connect(self.process_multiple_data)
        main_layout.addWidget(self.multi_run_btn)

        self.setLayout(main_layout)


    def browse_file(self, edit_widget, title, filter):
        """通用文件浏览"""
        filename, _ = QFileDialog.getOpenFileName(self, title, "", filter)
        if filename:
            edit_widget.setText(filename)

    def select_output_folder(self):
        """选择输出文件夹"""
        folder = QFileDialog.getExistingDirectory(self, "选择输出文件夹", "")
        if folder:
            self.output_edit.setText(folder)

    def browse_multiple_files(self):
        """浏览多个文件（修改分隔符处理）"""
        filenames, _ = QFileDialog.getOpenFileNames(self, "选择多个植被指数影像", "", "TIFF (*.tif)")
        if filenames:
            current_text = self.multi_precomp_edit.toPlainText()
            # 优化分隔符逻辑
            separator = ";\n" if current_text else ""
            formatted_files = ";\n".join(filenames)
            self.multi_precomp_edit.setText(current_text + separator + formatted_files)

    def validate_inputs(self, mode):
        """根据模式验证输入（新增输出文件夹验证）"""
        errors = []
        
        # ===== 新增输出文件夹验证 =====
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

        # ===== 原有矢量文件验证 =====
        shp_path = self.shp_edit.text().strip()
        if not shp_path:
            errors.append("必须指定矢量文件")
        else:
            if not shp_path.endswith('.shp'):
                errors.append("矢量文件格式错误，请选择.shp文件")
            elif not os.path.exists(shp_path):
                errors.append("矢量文件路径不存在")

        # ===== 根据模式验证影像文件 =====
        if mode == 'single':
            image_path = self.single_precomp_edit.text().strip()
            if not image_path:
                errors.append("必须指定单张植被指数影像")
            else:
                if not image_path.endswith('.tif'):
                    errors.append("单张影像格式错误，请选择.tif文件")
                elif not os.path.exists(image_path):
                    errors.append("单张影像文件不存在")

        elif mode == 'multi':
            files_text = self.multi_precomp_edit.toPlainText().strip()
            if not files_text:
                errors.append("必须提供多张影像路径")
            else:
                files = [f.strip() for f in files_text.split(";\n") if f.strip()]
                if not files:
                    errors.append("没有有效的影像路径")
                else:
                    for i, file in enumerate(files, 1):
                        if not file.endswith('.tif'):
                            errors.append(f"第{i}个文件格式错误：{os.path.basename(file)}")
                        elif not os.path.exists(file):
                            errors.append(f"第{i}个文件不存在：{os.path.basename(file)}")

        # ===== 错误处理 =====
        if errors:
            error_msg = "发现以下问题：\n\n• " + "\n• ".join(errors)
            QMessageBox.critical(self, "输入验证失败", error_msg)
            return False
        
        return True

    def process_single_data(self):
        """处理单张植被指数影像"""
        image_path = self.single_precomp_edit.text()
        if self.validate_inputs('single'):
            self.process_data(image_path)

    def process_multiple_data(self):
        # 在方法开始时重置检查状态
        self.coordinate_system_checked = False  # 新增重置
        self.coordinate_conversion_choice = None
        
        """处理多张植被指数影像（完整修改版）"""
        if not self.validate_inputs('multi'):
            return
        
        # 重置坐标系转换选择状态
        self.coordinate_conversion_choice = None  # 新增
        
        files_text = self.multi_precomp_edit.toPlainText().strip()
        files = [f.strip() for f in files_text.split(";\n") if f.strip()]
        
        # ===== 新增：预处理坐标系检查 =====
        # 读取原始矢量数据
        original_gdf = gpd.read_file(self.shp_edit.text())
        
        # 检查第一个影像的坐标系
        first_image = files[0]
        with rasterio.open(first_image) as src:
            if original_gdf.crs != src.crs:
                reply = QMessageBox.question(
                    self,
                    "坐标系不一致",
                    f"矢量文件坐标系 ({original_gdf.crs}) 与第一个影像坐标系 ({src.crs}) 不一致，是否自动转换？\n\n"
                    "选择「是」将转换矢量文件到影像坐标系，并应用于后续所有影像处理。\n"
                    "选择「否」将使用原始坐标系进行叠加分析，可能产生位置偏差！",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.Yes
                )
                if reply == QMessageBox.Yes:
                    self.gdf = original_gdf.to_crs(src.crs)
                else:
                    self.gdf = original_gdf
            else:
                self.gdf = original_gdf
        
        # 后续处理循环中直接使用self.gdf
        for file in files:
            self.process_data(file, batch_mode=True)


    def check_and_convert_coordinate_system(self, image_path):
        """检查并转换坐标系（修正版）"""
        if not self.coordinate_system_checked:  # 使用正确的属性名
            gdf = gpd.read_file(self.shp_edit.text())
            
            with rasterio.open(image_path) as src:
                if gdf.crs != src.crs:
                    reply = QMessageBox.question(
                        self, 
                        "坐标系不一致", 
                        f"矢量文件坐标系 ({gdf.crs}) 与影像坐标系 ({src.crs}) 不一致，是否自动转换？\n\n"
                        "选择「否」将使用原始坐标系进行叠加分析，可能产生位置偏差！",
                        QMessageBox.Yes | QMessageBox.No,
                        QMessageBox.Yes
                    )
                    if reply == QMessageBox.Yes:
                        self.gdf = gdf.to_crs(src.crs)
                    else:
                        self.gdf = gdf
                    self.coordinate_system_checked = True  # 标记已检查

    def process_data(self, image_path, batch_mode=False):
        """完整的植被指数处理流程（修改后版本）"""
        try:
            # ===== 1. 直接使用实例变量中的矢量数据 =====
            if self.gdf is None:
                self.gdf = gpd.read_file(self.shp_edit.text())  # 初始化矢量数据
            
            # ===== 2. 准备统计容器 =====
            all_results = []
            error_count = 0
            total_zones = len(self.gdf)

            # ===== 3. 创建进度条 =====
            progress = QProgressDialog(
                "计算进度", 
                "取消", 
                0, 
                total_zones, 
                self
            )
            progress.setWindowTitle(f"处理 {os.path.basename(image_path)}")
            progress.setWindowModality(Qt.WindowModal)
            progress.setAutoClose(True)
            progress.setAutoReset(False)

            try:
                with rasterio.open(image_path) as src:
                    # ===== 4. 遍历所有矢量区域 =====
                    for idx, row in enumerate(self.gdf.itertuples(), 1):
                        if progress.wasCanceled():
                            QMessageBox.information(self, "提示", "用户已取消操作")
                            break

                        progress.setValue(idx)
                        progress.setLabelText(
                            f"正在处理 {idx}/{total_zones}\n"
                            f"当前区域: {getattr(row, 'name', f'Zone_{idx}')}\n"
                            f"影像文件: {os.path.basename(image_path)}"
                        )
                        QApplication.processEvents()

                        try:
                            geom = row.geometry
                            if not geom.is_valid:
                                error_count += 1
                                continue

                            # ===== 5. 执行掩膜操作 =====
                            masked, transform = mask(
                                src, 
                                [geom], 
                                crop=True, 
                                nodata=src.nodata,
                                all_touched=True
                            )
                            
                            # ===== 6. 数据预处理 =====
                            band_data = masked[0].astype(np.float32)
                            valid_mask = ~np.isnan(band_data)
                            if src.nodata is not None:
                                valid_mask &= (band_data != src.nodata)
                            valid_values = band_data[valid_mask]

                            # ===== 7. 构建统计结果 =====
                            stats = {
                                '影像文件': os.path.basename(image_path),
                                '区域ID': getattr(row, 'id', idx),
                                '区域名称': getattr(row, 'name', f'Zone_{idx}'),
                                '最小值': np.nan,
                                '最大值': np.nan,
                                '平均值': np.nan,
                                '中位数': np.nan,
                                '标准差': np.nan,
                                '有效像元数': 0,
                                '总像元数': masked[0].size,
                                '处理时间': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            }
                            
                            if valid_values.size > 0:
                                stats.update({
                                    '最小值': round(float(np.nanmin(valid_values)), 4),
                                    '最大值': round(float(np.nanmax(valid_values)), 4),
                                    '平均值': round(float(np.nanmean(valid_values)), 4),
                                    '中位数': round(float(np.nanmedian(valid_values)), 4),
                                    '标准差': round(float(np.nanstd(valid_values)), 4),
                                    '有效像元数': int(valid_values.size)
                                })
                            
                            all_results.append(stats)

                        except Exception as e:
                            error_count += 1
                            print(f"区域 {idx} 处理错误: {str(e)}")
                            traceback.print_exc()

                    # ===== 8. 保存结果 =====
                    if all_results:
                        base_name = os.path.splitext(os.path.basename(image_path))[0]
                        csv_filename = f"{base_name}_statistics.csv"
                        output_folder = self.output_edit.text().strip()
                        csv_path = os.path.join(output_folder, csv_filename)
                        
                        df = pd.DataFrame(all_results)
                        # 优化列顺序
                        column_order = [
                            '影像文件', '区域ID', '区域名称', 
                            '最小值', '最大值', '平均值', '中位数', '标准差',
                            '有效像元数', '总像元数', '处理时间'
                        ]
                        df[column_order].to_csv(
                            csv_path,
                            index=False,
                            encoding='utf_8_sig',
                            float_format="%.4f"
                        )

                        if not batch_mode:
                            success_msg = (f"成功处理 {len(all_results)} 个区域\n"
                                         f"保存路径：{csv_path}")
                            if error_count > 0:
                                success_msg += f"\n\n警告：{error_count} 个区域处理失败"
                            QMessageBox.information(self, "处理完成", success_msg)
                    else:
                        if not batch_mode:
                            QMessageBox.warning(self, "无数据", "未找到任何有效统计结果！")

            # ===== 异常处理 =====
            except rasterio.errors.RasterioIOError as e:
                error_msg = (f"无法读取栅格文件：{os.path.basename(image_path)}\n"
                           f"错误类型：{type(e).__name__}\n"
                           f"详细信息：{str(e)}")
                if not batch_mode:
                    QMessageBox.critical(self, "文件错误", error_msg)
                else:
                    print(f"批量处理错误: {error_msg}")  # 批量模式记录到控制台

            except Exception as e:
                error_msg = (f"处理 {os.path.basename(image_path)} 时发生未预期错误\n"
                           f"错误类型：{type(e).__name__}\n"
                           f"跟踪信息：\n{traceback.format_exc()}")
                if not batch_mode:
                    QMessageBox.critical(self, "系统错误", error_msg)
                else:
                    print(error_msg)  # 批量模式不弹窗，记录到控制台

            finally:
                progress.close()

        except PermissionError as e:
            error_msg = f"文件保存被拒绝：{e}\n请检查文件是否被其他程序打开"
            if not batch_mode:
                QMessageBox.critical(self, "权限错误", error_msg)
            else:
                print(error_msg)