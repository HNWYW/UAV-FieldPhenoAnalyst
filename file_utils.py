import pandas as pd
from PyQt5.QtWidgets import QFileDialog, QMessageBox

def save_results_to_file(df, parent_widget):
    options = QFileDialog.Options()
    file_name, _ = QFileDialog.getSaveFileName(
        parent_widget,
        "保存文件",
        "",
        "CSV Files (*.csv);;Excel Files (*.xlsx)",
        options=options
    )
    if file_name:
        try:
            if file_name.endswith(".csv"):
                df.to_csv(file_name, index=False)
            elif file_name.endswith(".xlsx"):
                df.to_excel(file_name, index=False)
            QMessageBox.information(parent_widget, "保存成功", f"数据已保存到 {file_name}")
        except Exception as e:
            QMessageBox.warning(parent_widget, "保存错误", f"保存文件失败：{e}")
