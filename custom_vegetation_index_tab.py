import os
import json
import numpy as np
import pandas as pd
import geopandas as gpd
import rasterio
from rasterio.mask import mask
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QGridLayout, QLabel, QLineEdit,
                             QTextEdit, QPushButton, QFileDialog, QCheckBox, QScrollArea,
                             QHBoxLayout, QMessageBox, QProgressDialog, QGroupBox)
from PyQt5.QtCore import Qt
import traceback
from datetime import datetime  # 新增此行
from typing import Dict, Callable  # 新增导入
from typing import Dict, Callable  # 新增类型提示导入
from typing import Dict, Any, Callable  # 添加 Any
from typing import Dict, Any, Callable, Optional  # 常用类型导入
import numpy as np
from PyQt5.QtWidgets import QCheckBox, QWidget  # 确保 Qt 类型导入
import profile

# 在文件最顶部的导入区域添加
import re  # 新增此行

class CustomVegetationIndexTab(QWidget):
    def __init__(self, main_window=None):  # 新增主窗口参数
            super().__init__()
            self.main_window = main_window  # 保存主窗口引用
            self.custom_counter = 1
            
            # 原初始化代码保持不变
            self.band_config = [
                ("Red", "红波段（Red）"),
                ("Green", "绿波段（Green）"),
                ("Blue", "蓝波段（Blue）"),
                ("RedEdge", "红边波段（RedEdge）"),
                ("NIR", "近红外波段（NIR）")
            ]
            self.band_mapping = {
                '红': 'Red', '绿': 'Green', '蓝': 'Blue',
                '红边': 'RedEdge', '近红外': 'NIR',
                'Red': 'Red', 'Green': 'Green', 'Blue': 'Blue',
                'RedEdge': 'RedEdge', 'NIR': 'NIR'
            }
            self.custom_indices_file = "custom_indices.json"
            self.band_edits: Dict[str, QLineEdit] = {}
            self.custom_indices: Dict[str, str] = {}
            self.veg_index_checks: Dict[str, Dict[str, Any]] = {}
            
            # 初始化界面
            self.init_ui()
            self.load_custom_indices()

    def init_ui(self):
        """初始化界面布局（紧凑垂直布局版本）"""
        # 主布局设置
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(15)

        # === 输入参数部分 ===
        input_group = QGroupBox("输入参数")
        input_grid = QGridLayout()
        current_row = 0

        # 矢量文件输入
        self.shp_label = QLabel("矢量文件 (shp):")
        self.shp_edit = QLineEdit()
        self.shp_edit.setMinimumWidth(200)
        self.shp_browse_btn = QPushButton("浏览")
        self.shp_browse_btn.setFixedWidth(80)
        self.shp_browse_btn.clicked.connect(lambda: self.browse_file(self.shp_edit, "矢量文件", "Shapefile (*.shp)"))
        input_grid.addWidget(self.shp_label, current_row, 0)
        input_grid.addWidget(self.shp_edit, current_row, 1)
        input_grid.addWidget(self.shp_browse_btn, current_row, 2)
        current_row += 1

        # === 波段输入区域 ===
        self.band_edits = {}
        for band_key, band_name in self.band_config:
            label = QLabel(f"{band_name}:")
            edit = QLineEdit()
            edit.setMinimumWidth(300)
            btn = QPushButton("浏览")
            btn.setFixedWidth(80)
            btn.clicked.connect(lambda _, b=band_key: self.browse_band_file(b))
            input_grid.addWidget(label, current_row, 0)
            input_grid.addWidget(edit, current_row, 1)
            input_grid.addWidget(btn, current_row, 2)
            self.band_edits[band_key] = edit
            current_row += 1

        input_group.setLayout(input_grid)
        main_layout.addWidget(input_group)

        # === 自定义植被指数区域 ===
        custom_group = QGroupBox("自定义植被指数（勾选需要计算的指数）")
        custom_group.setStyleSheet("QGroupBox { margin-top: 15px; }")
        custom_layout = QVBoxLayout()
        custom_layout.setContentsMargins(5, 15, 5, 5)

        # 输入区域
        input_box = QHBoxLayout()
        self.custom_formula_edit = QLineEdit()
        self.custom_formula_edit.setPlaceholderText("输入公式（示例：NDVI=(NIR-Red)/(NIR+Red)）")
        
        # 提示标签
        hint_lines = [
            "支持中文/英文波段名：",
            "红(Red), 绿(Green), 蓝(Blue), 红边(RedEdge), 近红外(NIR)"
        ]
        hint_label = QLabel(" | ".join(hint_lines))
        hint_label.setStyleSheet("""
            QLabel {
                color: #666;
                font-size: 9pt;
                margin-left: 10px;
            }
        """)

        # 添加按钮
        self.add_custom_btn = QPushButton("添加公式")
        self.add_custom_btn.setFixedWidth(100)
        self.add_custom_btn.setStyleSheet("QPushButton { padding: 5px; }")

        input_box.addWidget(self.custom_formula_edit, 4)
        input_box.addWidget(hint_label, 3)
        input_box.addWidget(self.add_custom_btn, 1)
        custom_layout.addLayout(input_box)

        # === 已保存指数滚动区域 ===
        self.custom_scroll = QScrollArea()
        self.custom_scroll.setWidgetResizable(True)
        self.custom_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.custom_scroll.setStyleSheet("""
            QScrollArea { 
                border: 1px solid #ddd;
                border-radius: 4px;
                background: #f8f8f8;
            }
        """)
        
        # 容器布局
        self.custom_container = QWidget()
        self.custom_layout_area = QVBoxLayout(self.custom_container)
        self.custom_layout_area.setContentsMargins(5, 5, 5, 5)
        self.custom_layout_area.setSpacing(3)
        self.custom_layout_area.addStretch()  # 添加底部弹簧
        
        self.custom_scroll.setWidget(self.custom_container)
        custom_layout.addWidget(self.custom_scroll, 1)

        custom_group.setLayout(custom_layout)
        main_layout.addWidget(custom_group, 1)
        
        # === 输出设置 ===
        output_group = QGroupBox("输出设置")
        output_layout = QHBoxLayout()
        self.output_label = QLabel("输出文件夹:")
        self.output_edit = QLineEdit()
        self.output_btn = QPushButton("浏览")
        self.output_btn.clicked.connect(self.select_output_folder)  # 连接到选择文件夹的函数
        output_layout.addWidget(self.output_label)
        output_layout.addWidget(self.output_edit)
        output_layout.addWidget(self.output_btn)
        output_group.setLayout(output_layout)

        # 确保输出设置区域可见
        output_group.setVisible(True)

        # 将输出设置添加到主布局中
        main_layout.addWidget(output_group)

        # === 运行按钮 ===
        self.run_btn = QPushButton("▶ 开始计算所有勾选的植被指数")
        self.run_btn.setStyleSheet("""
            QPushButton {
                font-size:12pt; 
                padding:8px; 
                background:#4CAF50; 
                color:white;
            }
            QPushButton:hover{background:#45a049;}
        """)
        main_layout.addWidget(self.run_btn)

        # 信号连接
        self.add_custom_btn.clicked.connect(self.add_custom_index)
        self.run_btn.clicked.connect(self.process_data)

        # 设置主布局
        self.setLayout(main_layout)

    
    def select_output_folder(self):
        """选择输出文件夹"""
        folder_path = QFileDialog.getExistingDirectory(self, "选择输出文件夹")
        if folder_path:
            self.output_edit.setText(folder_path)  # Set the selected folder path in the output edit field

    
    def browse_file(self, edit_widget, title, filter):
        """通用文件浏览"""
        filename, _ = QFileDialog.getOpenFileName(self, title, "", filter)
        if filename:
            edit_widget.setText(filename)

    def browse_band_file(self, band_type):  # band_type现在接收大写的键（如"Red"）
        filename, _ = QFileDialog.getOpenFileName(
            self,
            f"选择{self.band_config[[b[0] for b in self.band_config].index(band_type)][1]}文件",
            "", 
            "TIFF (*.tif)"
        )
        if filename:
            self.band_edits[band_type].setText(filename)
            
            
    def load_custom_indices(self):
        """加载保存的自定义指数（完整代码含状态栏修改）"""
        try:
            # 清理现有非临时组件
            for name in list(self.veg_index_checks.keys()):
                item = self.veg_index_checks[name]
                if not item.get('temporary', False):
                    if 'container' in item:
                        item['container'].deleteLater()
                    del self.veg_index_checks[name]

            # 如果配置文件不存在则跳过加载
            if not os.path.exists(self.custom_indices_file):
                return

            # 增强文件读取异常处理
            try:
                with open(self.custom_indices_file, "r", encoding="utf-8") as f:
                    raw_data = f.read()
                    # 处理空文件情况
                    if not raw_data.strip():
                        self.custom_indices = {}
                    else:
                        self.custom_indices = json.loads(raw_data)
            except json.JSONDecodeError as e:
                QMessageBox.critical(
                    self,
                    "配置文件损坏",
                    f"无法解析自定义指数文件：\n{str(e)}\n\n"
                    f"建议：删除或修复 {os.path.abspath(self.custom_indices_file)}"
                )
                return
            except Exception as e:
                QMessageBox.critical(
                    self,
                    "文件读取失败",
                    f"加载自定义指数失败：{str(e)}\n"
                    f"文件路径：{os.path.abspath(self.custom_indices_file)}"
                )
                return

            # 按保存顺序加载指数
            loaded_count = 0
            for index_name in self.custom_indices:
                try:
                    formula = self.custom_indices[index_name]
                    
                    # 有效性检查
                    if not isinstance(formula, str) or not formula:
                        QMessageBox.warning(
                            self,
                            "无效条目",
                            f"跳过无效指数：{index_name} (公式格式错误)"
                        )
                        continue
                    
                    # 名称合法性检查
                    if not re.match(r'^[a-zA-Z_][\w-]{1,31}$', index_name):
                        QMessageBox.warning(
                            self,
                            "非法名称",
                            f"跳过非法指数名称：{index_name}\n"
                            "名称需满足：字母/下划线开头，2-32字符"
                        )
                        continue
                    
                    # 创建组件（新增重复检查）
                    if index_name in self.veg_index_checks:
                        QMessageBox.warning(
                            self,
                            "重复指数",
                            f"跳过重复指数：{index_name} (已存在同名指数)"
                        )
                        continue
                    
                    self._create_custom_widget(index_name, formula)
                    loaded_count += 1
                except Exception as e:
                    traceback.print_exc()
                    QMessageBox.warning(
                        self,
                        "加载异常",
                        f"加载指数 {index_name} 失败：{str(e)}\n详见控制台日志"
                    )

            # === 状态栏反馈（关键修改点）===
            if loaded_count > 0:
                status = f"成功加载 {loaded_count}/{len(self.custom_indices)} 个自定义指数"
            else:
                status = "未找到有效自定义指数"
            
            # 通过主窗口显示状态（新增安全判断）
            if self.main_window and hasattr(self.main_window, 'statusBar'):
                self.main_window.statusBar().showMessage(status, 5000)
            else:
                print(f"[调试] 状态栏不可用：{status}")  # 开发阶段保留调试输出

        except Exception as e:
            QMessageBox.critical(
                self,
                "加载崩溃",
                f"加载过程发生严重错误：{str(e)}\n{traceback.format_exc()}"
            )
            
    def save_custom_indices(self):
        """保存自定义指数到文件"""
        try:
            with open(self.custom_indices_file, "w", encoding="utf-8") as f:
                json.dump(self.custom_indices, f, ensure_ascii=False, indent=2)
        except Exception as e:
            QMessageBox.warning(self, "错误", f"保存失败: {str(e)}")

    def add_custom_index(self):
        """添加自定义植被指数（完整代码，无省略）"""
        try:
            # === 步骤1：获取原始输入并校验 ===
            raw_input = self.custom_formula_edit.text().strip()
            if not raw_input:
                QMessageBox.warning(self, "输入错误", "公式不能为空！")
                return

            # === 步骤2：解析公式名称和表达式 ===
            index_name = None
            formula = raw_input
            if '=' in raw_input:
                parts = raw_input.split('=', 1)  # 仅分割第一个等号
                index_name_part = parts[0].strip()
                formula_part = parts[1].strip()
                
                # 检查是否为空名称（例如输入"=A+B"的情况）
                if index_name_part:
                    index_name = index_name_part
                    formula = formula_part
                else:
                    QMessageBox.warning(self, "格式错误", "名称不能为空！\n正确格式：名称=公式")
                    return

            # === 步骤3：自动生成唯一名称 ===
            if not index_name:
                # 获取所有Custom_编号
                existing_customs = [name for name in self.custom_indices.keys() if name.startswith("Custom_")]
                existing_numbers = []
                for name in existing_customs:
                    try:
                        num = int(name.split("_")[1])
                        existing_numbers.append(num)
                    except (IndexError, ValueError):
                        continue  # 忽略非法格式
                
                # 计算下一个可用编号
                next_num = max(existing_numbers) + 1 if existing_numbers else 1
                
                # 确保编号未被占用（处理手动创建Custom_的情况）
                while True:
                    candidate_name = f"Custom_{next_num}"
                    if candidate_name not in self.custom_indices:
                        index_name = candidate_name
                        break
                    next_num += 1

            # === 步骤4：验证名称合法性 ===
            if not re.match(r'^[a-zA-Z_][\w-]{1,31}$', index_name):
                QMessageBox.warning(
                    self, 
                    "非法名称", 
                    "名称需满足：\n"
                    "1. 以字母/下划线开头\n"
                    "2. 只能包含字母、数字、下划线和短横线\n"
                    "3. 长度2-32字符\n"
                    f"当前名称：{index_name}"
                )
                return

            # === 步骤5：公式预处理 ===
            original_formula = formula  # 保留原始公式（含空格和中文）
            processed_formula = formula.replace(" ", "").replace("（", "(").replace("）", ")")  # 去除空格和全角括号
            processed_formula = self._convert_chinese_bands(processed_formula)  # 转换中文波段名

            # === 步骤6：处理 sqrt 函数 ===
            # 将 sqrt 替换为 np.sqrt
            processed_formula = processed_formula.replace("sqrt", "np.sqrt")  # 将 sqrt 转换为 np.sqrt

            # === 步骤7：公式验证 ===
            try:
                # 允许的符号和波段
                allowed_symbols = set("+-*/()_.^0123456789")  # 包含幂运算符^
                valid_bands = list(self.band_mapping.values())
                
                # 提取公式中的变量
                variables = re.findall(r'\b([a-zA-Z_]+)\b', processed_formula)
                variables = [var for var in variables if not var.isdigit()]  # 排除数字
                
                # 验证变量有效性
                invalid_vars = []
                for var in variables:
                    var_upper = var.upper()
                    if var_upper not in [b.upper() for b in valid_bands]:
                        invalid_vars.append(var)
                        
                if invalid_vars:
                    valid_bands_display = [f"{chn}（{en}）" for chn, en in self.band_mapping.items() if len(chn) > 1]
                    raise NameError(
                        f"未识别的变量：{', '.join(invalid_vars)}\n"
                        f"有效波段：{', '.join(valid_bands_display)}"
                    )
                
                # 符号有效性检查
                for char in processed_formula:
                    if char.isalnum() or char in allowed_symbols:
                        continue
                    raise SyntaxError(f"非法字符：'{char}'")

                # 数学安全性验证（使用大写变量）
                dummy_data = {var.upper(): np.array([1.0]) for var in variables}
                
                # 显式传递 np 到 eval 的上下文
                eval(processed_formula.upper(), {"__builtins__": None, "np": np}, dummy_data)

            except Exception as e:
                error_detail = (
                    f"公式验证失败：{str(e)}\n"
                    f"原始公式：{original_formula}\n"
                    f"处理后公式：{processed_formula}\n"
                    "允许符号：+ - * / ( ) . ^ 0-9\n"
                    "有效波段变量："
                    f"{', '.join([f'{chn}（{en}）' for chn, en in self.band_mapping.items() if len(chn) > 1])}"
                )
                QMessageBox.warning(self, "公式错误", error_detail)
                return

            # === 步骤7：保存确认对话框 ===
            save_reply = QMessageBox.question(
                self, 
                "保存确认", 
                f"是否保存该指数？\n\n名称：{index_name}\n公式：{original_formula}",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
                QMessageBox.Yes
            )

            if save_reply == QMessageBox.Cancel:
                return  # 用户取消操作
            elif save_reply == QMessageBox.Yes:
                # 检查名称唯一性（可能在对话框弹出后被其他操作修改）
                if index_name in self.custom_indices:
                    QMessageBox.warning(
                        self, 
                        "名称冲突", 
                        f"名称 '{index_name}' 已存在！\n"
                        "可能原因：\n"
                        "1. 其他用户同时修改了配置文件\n"
                        "2. 程序内部状态不一致"
                    )
                    return

                # 添加到持久化存储
                self.custom_indices[index_name] = original_formula
                self.save_custom_indices()

            # === 步骤8：创建界面组件 ===
            # 检查是否已存在同名组件（极少数并发情况）
            existing_widget = self.veg_index_checks.get(index_name)
            if existing_widget:
                QMessageBox.warning(
                    self, 
                    "组件冲突", 
                    f"'{index_name}' 组件已存在，将替换旧版本"
                )
                existing_widget['container'].deleteLater()
                del self.veg_index_checks[index_name]

            # 创建新组件
            self._create_custom_widget(index_name, original_formula)

            # 标记临时指数
            if save_reply == QMessageBox.No:
                self.veg_index_checks[index_name]['temporary'] = True
                self.veg_index_checks[index_name]['checkbox'].setText(
                    f"[临时] {index_name} = {original_formula}"
                )
                self.veg_index_checks[index_name]['checkbox'].setStyleSheet(
                    "color: #666; font-style: italic;"
                )

            # 清空输入框
            self.custom_formula_edit.clear()

        except Exception as e:
            error_msg = (
                f"添加指数时发生未预期错误\n"
                f"类型：{type(e).__name__}\n"
                f"信息：{str(e)}\n"
                f"追踪：\n{traceback.format_exc()}"
            )
            QMessageBox.critical(
                self, 
                "系统错误", 
                error_msg
            )
            
    def _convert_chinese_bands(self, formula: str) -> str:
        """将中文波段名称转换为英文标识，保留英文部分的大小写"""
        chinese_pattern = re.compile(r'([\u4e00-\u9fa5]+)')
        
        def replace_handler(match: re.Match) -> str:
            chn_name = match.group(1)
            return self.band_mapping.get(chn_name, chn_name)
        
        # 仅替换中文部分，英文部分保留原样
        return chinese_pattern.sub(replace_handler, formula)

        
    def _create_custom_widget(self, name: str, formula: str) -> None:
            """创建自定义指数组件（完整代码）"""
            try:
                # 容器设置
                container = QWidget()
                container.setFixedHeight(28)
                layout = QHBoxLayout(container)
                layout.setContentsMargins(5, 1, 5, 1)
                layout.setSpacing(8)

                # 复选框
                cb = QCheckBox()
                cb.setStyleSheet("""
                    QCheckBox { font: 9pt "Microsoft YaHei"; color: #333; margin-left: 2px; }
                    QCheckBox::indicator { width: 16px; height: 16px; }
                """)
                display_text = f"{name} = {formula}"
                cb.setText(display_text[:50] + "..." if len(display_text) > 50 else display_text)
                cb.setToolTip(f"{name} = {formula}")

                # 删除按钮
                del_btn = QPushButton("×")
                del_btn.setFixedSize(18, 18)
                del_btn.setStyleSheet("""
                    QPushButton {
                        font: bold 12px; color: #ff4444; border: none; 
                        background: transparent; padding: 0px; margin-right: 2px;
                    }
                    QPushButton:hover { color: #ff0000; background: #ffeeee; }
                """)
                del_btn.clicked.connect(lambda: self.remove_custom_index(name, container))

                # 布局
                layout.addWidget(cb, stretch=4)
                layout.addStretch(stretch=1)
                layout.addWidget(del_btn, stretch=1)

                # 公式处理
                processed_formula = formula.replace(" ", "").replace("（", "(").replace("）", ")")
                processed_formula = self._convert_chinese_bands(processed_formula)

                # 计算函数
                def formula_generator(formula_str: str):
                    def calculate(**bands):
                        try:
                            validated_bands = {}
                            for k, v in bands.items():
                                v = np.array(v, dtype=np.float32)
                                validated_bands[k.upper()] = np.where(
                                    (v < 0) | (v > 1) | np.isnan(v), np.nan, v
                                )
                            with np.errstate(all='ignore'):
                                result = eval(
                                    formula_str.upper(),
                                    {"__builtins__": None},
                                    {k.upper(): v for k, v in validated_bands.items()}
                                )
                                return np.clip(np.nan_to_num(result, nan=np.nan), -1.0, 1.0)
                        except Exception as e:
                            print(f"[{name}] 计算错误: {str(e)}\nFormula: {formula_str}")
                            return np.full_like(next(iter(bands.values())), np.nan)
                    return calculate

                # 存储元数据
                self.veg_index_checks[name] = {
                    'checkbox': cb,
                    'formula_func': formula_generator(processed_formula),
                    'formula_text': formula,
                    'container': container,
                    'processed_formula': processed_formula
                }

                # 添加到布局
                items_count = self.custom_layout_area.count()
                if items_count > 0 and isinstance(self.custom_layout_area.itemAt(items_count-1).widget(), QWidget):
                    self.custom_layout_area.insertWidget(items_count-1, container)
                else:
                    self.custom_layout_area.addWidget(container)

            except Exception as e:
                QMessageBox.critical(
                    self,
                    "组件创建错误",
                    f"创建组件失败: {name}\nError: {str(e)}\nTraceback:\n{traceback.format_exc()}"
                )

    def remove_custom_index(self, name, widget):
        """删除自定义指数（增强版）"""
        reply = QMessageBox.question(
            self, 
            "确认删除", 
            f"确定删除该指数吗？\n名称：{name}\n公式：{self.veg_index_checks[name]['formula_text']}",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # 从所有存储结构中移除
            self.custom_indices.pop(name, None)
            self.veg_index_checks.pop(name, None)
            self.save_custom_indices()
            widget.deleteLater()

            # 如果是临时指数，立即刷新界面
            if hasattr(self, 'temporary'):
                self.custom_widget.update()

    def validate_inputs(self):
        errors = []
        # 检查矢量文件
        if not self.shp_edit.text().endswith('.shp'):
            errors.append("请选择有效的矢量文件(.shp)")
        
        # 修改为仅检查波段输入（删除预合成检查）
        has_bands = any(edit.text() for edit in self.band_edits.values())
        if not has_bands:
            errors.append("必须提供至少一个波段文件")
        
        if errors:
            QMessageBox.critical(self, "输入错误", "\n".join(errors))
            return False
        return True

    def process_data(self):
        """处理数据并自动保存到指定输出文件夹"""
        try:
            # ===== 1. 输入验证 =====
            if not self.validate_inputs():
                return

            # ===== 2. 准备输出目录 =====
            output_dir = self.output_edit.text().strip()
            if not output_dir:
                QMessageBox.critical(self, "错误", "必须指定输出文件夹！")
                return

            # 创建输出目录
            os.makedirs(output_dir, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            final_output_dir = os.path.join(output_dir, f"VegetationIndices_{timestamp}")
            os.makedirs(final_output_dir, exist_ok=True)

            # ===== 3. 准备基础数据 =====
            shp_path = self.shp_edit.text()
            try:
                gdf = gpd.read_file(shp_path)
            except Exception as e:
                QMessageBox.critical(self, "矢量文件错误", f"无法读取矢量文件：\n{str(e)}")
                return

            # ===== 4. 加载波段数据 =====
            band_data = {}
            crs = None
            transform = None
            width = height = 0

            for band_key, edit in self.band_edits.items():
                file_path = edit.text()
                if not file_path:
                    continue

                try:
                    with rasterio.open(file_path) as src:
                        data = src.read(1).astype('float32')
                        data = np.where(
                            (data == src.nodata) | (data < 0) | (data > 1),
                            np.nan,
                            data
                        )

                        if crs is None:
                            crs = src.crs
                            transform = src.transform
                            width = src.width
                            height = src.height
                        elif src.crs != crs:
                            QMessageBox.critical(
                                self, "坐标系错误",
                                f"{self.band_config[[b[0] for b in self.band_config].index(band_key)][1]}"
                                f"的坐标系({src.crs})与其他波段不一致！"
                            )
                            return

                        band_data[band_key] = data

                except Exception as e:
                    QMessageBox.critical(
                        self, "文件读取错误",
                        f"{self.band_config[[b[0] for b in self.band_config].index(band_key)][1]}"
                        f"文件读取失败：\n{str(e)}"
                    )
                    return

            # ===== 5. 批量处理指数 =====
            selected_indices = [
                name for name, data in self.veg_index_checks.items()
                if data['checkbox'].isChecked()
            ]

            # 进度条设置
            progress = QProgressDialog("处理进度", "取消", 0, len(selected_indices), self)
            progress.setWindowTitle("正在处理")
            progress.setWindowModality(Qt.WindowModal)
            progress.show()

            success_count = 0
            error_log = []

            for i, index_name in enumerate(selected_indices):
                if progress.wasCanceled():
                    break
                progress.setValue(i)
                progress.setLabelText(f"正在处理 {index_name} ({i+1}/{len(selected_indices)})")

                try:
                    # ===== 生成文件路径 =====
                    tif_filename = f"{index_name}.tif"
                    tif_path = os.path.join(final_output_dir, tif_filename)
                    csv_filename = f"{index_name}_统计结果.csv"
                    csv_path = os.path.join(final_output_dir, csv_filename)

                    # ===== 检查文件存在性 =====
                    overwrite = False
                    if os.path.exists(tif_path) or os.path.exists(csv_path):
                        reply = QMessageBox.question(
                            self,
                            "文件已存在",
                            f"以下文件已存在，是否覆盖？\n{tif_filename}\n{csv_filename}",
                            QMessageBox.Yes | QMessageBox.No
                        )
                        if reply == QMessageBox.No:
                            error_log.append(f"{index_name}: 用户跳过覆盖已存在文件")
                            continue
                        overwrite = True

                    # ===== 执行计算 =====
                    index_data = self.veg_index_checks.get(index_name)
                    if not index_data:
                        error_log.append(f"{index_name}: 配置信息丢失")
                        continue

                    formula_func = index_data['formula_func']
                    formula_text = index_data['formula_text']

                    required_bands = re.findall(r'\b(Red|Green|Blue|RedEdge|NIR)\b', formula_text)
                    params = {band: band_data[band] for band in required_bands}

                    result = formula_func(**params)
                    result = np.where(np.isinf(result), np.nan, result)
                    result = np.nan_to_num(result, nan=np.nan)

                    # ===== 保存TIFF =====
                    profile = {
                        'driver': 'GTiff',
                        'width': width,
                        'height': height,
                        'count': 1,
                        'dtype': rasterio.float32,
                        'crs': crs,
                        'transform': transform,
                        'nodata': np.nan
                    }
                    with rasterio.open(tif_path, 'w', **profile) as dst:
                        dst.write(result, 1)

                    # ===== 统计并保存CSV =====
                    stats_data = []
                    with rasterio.open(tif_path) as src:
                        from shapely.geometry import box
                        bbox = src.bounds
                        bbox_polygon = box(bbox.left, bbox.bottom, bbox.right, bbox.top)

                        gdf_filtered = gdf.to_crs(src.crs)
                        gdf_filtered = gdf_filtered[gdf_filtered.geometry.intersects(bbox_polygon)]

                        for idx, row in gdf_filtered.iterrows():
                            try:
                                geom = row.geometry
                                if not geom.is_valid:
                                    geom = geom.buffer(0)
                                    if not geom.is_valid:
                                        continue

                                masked, _ = mask(src, [geom], crop=True, nodata=np.nan)
                                data = masked[0].astype('float32')
                                valid_data = data[~np.isnan(data)]

                                if valid_data.size > 0:
                                    stats = {
                                        '指数名称': index_name,
                                        '区域ID': row.get('id', idx+1),
                                        '区域名称': row.get('name', f'区域_{idx+1}'),
                                        '最小值': np.nanmin(valid_data),
                                        '最大值': np.nanmax(valid_data),
                                        '平均值': np.nanmean(valid_data),
                                        '中位数': np.nanmedian(valid_data),
                                        '标准差': np.nanstd(valid_data),
                                        '有效像元数': valid_data.size,
                                        '总像元数': data.size
                                    }
                                else:
                                    stats = {
                                        '指数名称': index_name,
                                        '区域ID': row.get('id', idx+1),
                                        '区域名称': row.get('name', f'区域_{idx+1}'),
                                        '最小值': np.nan,
                                        '最大值': np.nan,
                                        '平均值': np.nan,
                                        '中位数': np.nan,
                                        '标准差': np.nan,
                                        '有效像元数': 0,
                                        '总像元数': data.size
                                    }
                                stats_data.append(stats)
                            except Exception as e:
                                error_log.append(f"{index_name} 区域{idx+1}统计失败：{str(e)}")
                                continue

                    # ===== 保存CSV =====
                    if stats_data:
                        try:
                            df = pd.DataFrame(stats_data)
                            df.to_csv(
                                csv_path,
                                index=False,
                                encoding='utf_8_sig',
                                float_format="%.4f"
                            )
                            success_count += 1
                        except Exception as e:
                            error_log.append(f"{index_name} CSV保存失败：{str(e)}\n路径：{csv_path}")
                    else:
                        error_log.append(f"{index_name} 无有效统计结果")

                except Exception as e:
                    error_log.append(f"{index_name} 处理失败：{str(e)}\n{traceback.format_exc()}")

            progress.close()

            # ===== 6. 结果报告 =====
            report = f"处理完成！\n输出目录：{final_output_dir}\n成功指数：{success_count}个"
            if error_log:
                error_log_path = os.path.join(final_output_dir, "processing_errors.log")
                with open(error_log_path, "w", encoding="utf-8") as f:
                    f.write("\n".join(error_log))
                report += f"\n遇到{len(error_log)}个错误，详见：{error_log_path}"

            QMessageBox.information(
                self,
                "处理完成",
                report,
                QMessageBox.Ok
            )

        except Exception as e:
            QMessageBox.critical(
                self,
                "全局错误",
                f"发生未预期错误：\n{str(e)}\n\n跟踪信息：\n{traceback.format_exc()}"
            )

    def _batch_process(self, indices: list, output_dir: str):
        """批量处理核心逻辑"""
        try:
            # 加载矢量数据
            shp_path = self.shp_edit.text()
            gdf = gpd.read_file(shp_path)

            # 加载波段数据
            band_data = {}
            crs = None
            transform = None
            width = height = 0

            for band_key, edit in self.band_edits.items():
                file_path = edit.text()
                if not file_path:
                    continue

                with rasterio.open(file_path) as src:
                    data = src.read(1).astype('float32')
                    data = np.where(
                        (data == src.nodata) | (data < 0) | (data > 1),
                        np.nan,
                        data
                    )

                    if crs is None:
                        crs = src.crs
                        transform = src.transform
                        width = src.width
                        height = src.height
                    elif src.crs != crs:
                        raise ValueError(f"{band_key}波段坐标系不一致")

                    band_data[band_key] = data

            # 处理每个指数
            for index_name in indices:
                index_data = self.veg_index_checks.get(index_name)
                if not index_data:
                    continue

                # 生成文件路径
                tif_path = os.path.join(output_dir, f"{index_name}.tif")
                csv_path = os.path.join(output_dir, f"{index_name}_统计结果.csv")

                # 计算指数
                formula_func = index_data['formula_func']
                required_bands = re.findall(r'\b(Red|Green|Blue|RedEdge|NIR)\b', index_data['processed_formula'])
                params = {band: band_data[band] for band in required_bands}
                result = formula_func(**params)

                # 保存TIFF
                profile = {
                    'driver': 'GTiff',
                    'width': width,
                    'height': height,
                    'count': 1,
                    'dtype': rasterio.float32,
                    'crs': crs,
                    'transform': transform,
                    'nodata': np.nan
                }
                with rasterio.open(tif_path, 'w', **profile) as dst:
                    dst.write(result, 1)

                # 统计结果（示例，需完善）
                stats = {
                    'min': np.nanmin(result),
                    'max': np.nanmax(result),
                    'mean': np.nanmean(result)
                }
                pd.DataFrame([stats]).to_csv(csv_path, index=False)

        except Exception as e:
            QMessageBox.critical(
                self,
                "批量处理错误",
                f"发生未处理错误：{str(e)}\n{traceback.format_exc()}"
            )