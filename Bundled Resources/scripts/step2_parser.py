import json
import os
import pandas as pd
import pymupdf
import PyPDF2 as pypdf2  # 添加 pypdf2 作为备用 PDF 解析器
from langchain_text_splitters import RecursiveCharacterTextSplitter
from typing import Optional

from config import (
    RAW_DATA_DIR,
    NEW_CHUNKS_FILE,
    PROCESSED_RECORD,
    CHUNK_SIZE,
    CHUNK_OVERLAP,
    CHUNK_SEPARATORS,
)


# 初始化文本分割器
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=CHUNK_SIZE,
    chunk_overlap=CHUNK_OVERLAP,
    separators=CHUNK_SEPARATORS,
)


def parse_pdf(file_path: str) -> Optional[str]:
    """
    解析 PDF 文件（增强版，使用多解析器备选）
    返回: 文本内容，失败时返回 None
    """
    text = ""

    # 尝试使用 pypdf2 作为首选（更健壮）
    try:
        import pypdf2
        doc = pypdf2.PdfReader(file_path)
        for page in doc.pages:
            try:
                page_text = page.extract_text()
                if page_text.strip():  # 只添加非空页面
                    text += page_text + "\n"
            except Exception as e:
                print(f"     ⚠️ 页面提取失败: {e}")
                continue
        return text if text.strip() else None

    except Exception as e1:
        # pypdf2 失败，尝试使用 pymupdf 作为备选
        print(f"     🔄 pypdf2 失败，尝试 pymupdf: {e1}")
        try:
            doc = pymupdf.open(file_path)
            for page in doc:
                page_text = page.get_text()
                if page_text.strip():
                    text += page_text + "\n"
            doc.close()
            return text if text.strip() else None

        except pymupdf.PdfError as e2:
            print(f"     ⚠️ PDF 解析失败 {os.path.basename(file_path)}: {e2}")
            return None
        except Exception as e2:
            print(f"     ⚠️ PDF 读取异常 {os.path.basename(file_path)}: {e2}")
            return None


def parse_excel(file_path: str) -> Optional[str]:
    """
    解析 Excel 文件
    返回: 文本内容，失败时返回 None
    """
    text = ""
    try:
        excel_data = pd.read_excel(file_path, sheet_name=None)
        for sheet_name, df in excel_data.items():
            # 跳过空的 sheet
            if df.empty:
                continue

            text += f"\n\n### Excel 表格名: {sheet_name}\n"
            # 填充 NaN 为空字符串，避免 markdown 转换问题
            text += df.fillna("").to_markdown(index=False) + "\n"

        if not text.strip():
            print(f"     ⚠️ Excel 内容为空: {os.path.basename(file_path)}")
            return None

    except pd.errors.EmptyDataError:
        print(f"     ⚠️ Excel 文件为空: {os.path.basename(file_path)}")
        return None
    except pd.errors.ParserError as e:
        print(f"     ⚠️ Excel 解析失败 {os.path.basename(file_path)}: {e}")
        return None
    except Exception as e:
        print(f"     ⚠️ 读取 Excel 异常 {os.path.basename(file_path)}: {e}")
        return None

    return text


def read_txt_file(file_path: str) -> Optional[str]:
    """
    读取文本文件
    返回: 文件内容，失败时返回 None
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        if not content.strip():
            print(f"     ⚠️ 文本文件为空: {os.path.basename(file_path)}")
            return None

        return content

    except UnicodeDecodeError:
        # 尝试其他编码
        try:
            with open(file_path, "r", encoding="gbk") as f:
                content = f.read()
            if content.strip():
                return content
            return None
        except Exception as e:
            print(f"     ⚠️ 文本文件编码错误 {os.path.basename(file_path)}: {e}")
            return None
    except (IOError, OSError) as e:
        print(f"     ⚠️ 读取文本文件失败 {os.path.basename(file_path)}: {e}")
        return None


def load_processed_folders() -> set[str]:
    """读取已处理过的文件夹记录"""
    if not os.path.exists(PROCESSED_RECORD):
        return set()

    try:
        with open(PROCESSED_RECORD, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return set(data)
            print(f"⚠️ processed_folders.json 格式异常，重建记录")
            return set()
    except (json.JSONDecodeError, IOError) as e:
        print(f"⚠️ 读取处理记录失败，重建记录: {e}")
        return set()


def save_processed_folders(processed_set: set[str]) -> bool:
    """
    保存处理记录
    返回: 是否成功
    """
    try:
        with open(PROCESSED_RECORD, "w", encoding="utf-8") as f:
            json.dump(list(processed_set), f, ensure_ascii=False, indent=2)
        return True
    except (IOError, OSError) as e:
        print(f"❌ 保存处理记录失败: {e}")
        return False


def extract_metadata_from_folder_name(folder_name: str) -> tuple[str, str]:
    """
    从文件夹名提取邮件日期和主题
    格式: YYYY-MM-DD_subject
    返回: (date, subject)
    """
    parts = folder_name.split("_", 1)
    if len(parts) == 2:
        return parts[0], parts[1]
    return "Unknown Date", folder_name


def run_parser() -> int:
    """
    运行增量文档解析
    返回: 成功处理的文件夹数量
    """
    print("🧠 初始化增量文档解析引擎...")

    if not os.path.exists(RAW_DATA_DIR):
        print("❌ 找不到 raw_data 文件夹。请先运行 step1。")
        return 0

    # 加载已处理记录
    processed_folders = load_processed_folders()

    # 获取所有文件夹
    try:
        folder_names = [
            f for f in os.listdir(str(RAW_DATA_DIR))
            if os.path.isdir(os.path.join(str(RAW_DATA_DIR), f))
        ]
    except (OSError, IOError) as e:
        print(f"❌ 读取 raw_data 目录失败: {e}")
        return 0

    new_chunks = []
    newly_processed_count = 0
    skipped_count = 0

    for folder_name in folder_names:
        # 跳过已处理的文件夹
        if folder_name in processed_folders:
            skipped_count += 1
            continue

        folder_path = os.path.join(str(RAW_DATA_DIR), folder_name)
        email_date, email_subject = extract_metadata_from_folder_name(folder_name)

        print(f"  📄 解析新数据: {folder_name[:50]}...")

        # 处理文件夹中的文件
        for file_name in os.listdir(folder_path):
            file_path = os.path.join(folder_path, file_name)
            content = None

            # 根据文件类型选择解析方式
            if file_name.endswith(".txt"):
                content = read_txt_file(file_path)
            elif file_name.lower().endswith(".pdf"):
                content = parse_pdf(file_path)
            elif file_name.lower().endswith((".xlsx", ".xls")):
                content = parse_excel(file_path)

            # 跳过解析失败的文件
            if content is None:
                continue

            try:
                # 分块处理
                chunks = text_splitter.split_text(content)
                for i, chunk_text in enumerate(chunks):
                    new_chunks.append({
                        "source_email_date": email_date,
                        "source_email_subject": email_subject,
                        "source_file": file_name,
                        "chunk_index": i,
                        "content": chunk_text
                    })
            except Exception as e:
                print(f"     ⚠️ 分块处理失败 {file_name}: {e}")
                continue

        # 标记文件夹已处理
        processed_folders.add(folder_name)
        newly_processed_count += 1

    # 如果没有新数据，清理临时文件并退出
    if newly_processed_count == 0:
        print(f"✅ 没有需要解析的新文件夹，已跳过 {skipped_count} 个已处理文件夹。")
        if os.path.exists(NEW_CHUNKS_FILE):
            try:
                os.remove(NEW_CHUNKS_FILE)
            except OSError as e:
                print(f"⚠️ 删除临时文件失败: {e}")
        return 0

    # 保存新的知识块
    try:
        with open(NEW_CHUNKS_FILE, "w", encoding="utf-8") as f:
            json.dump(new_chunks, f, ensure_ascii=False, indent=2)

        # 保存处理记录
        save_processed_folders(processed_folders)

        print(f"\n🎉 增量解析完成！")
        print(f"   - 新增处理: {newly_processed_count} 个文件夹")
        print(f"   - 跳过已处理: {skipped_count} 个文件夹")
        print(f"   - 生成知识块: {len(new_chunks)} 个")

    except (IOError, OSError) as e:
        print(f"❌ 保存解析结果失败: {e}")
        return 0

    return newly_processed_count


if __name__ == "__main__":
    run_parser()
