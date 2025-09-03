import os
import logging
from lxml import etree

# 获取日志记录器
logger = logging.getLogger('subtitle_watcher')

def modify_xml(filepath):
    """
    修改XML文件，将body元素的type属性设置为subtitle，并添加sourceprovider标签
    返回值:
    - True: 文件被修改
    - False: 文件已符合要求
    - 'empty': 空白文件
    - 'error': 处理错误
    """
    try:
        # 检查文件是否为空
        if os.path.getsize(filepath) == 0:
            print(f"⚠️ 空白文件: {filepath}")
            return 'empty'
            
        # 解析XML文件
        tree = etree.parse(filepath)
        root = tree.getroot()
        
        modified = False
        
        # 查找所有body元素
        for elem in root.iter("body"):
            current_type = elem.get("type")
            if current_type != "subtitle":
                elem.set("type", "subtitle")
                modified = True
                # logger.info(f"✅ 修改body type: {current_type} -> subtitle in {filepath}")
        
        # 检查是否已存在sourceprovider标签
        sourceprovider_exists = False
        for elem in root.iter("sourceprovider"):
            sourceprovider_exists = True
            break
        
        # 如果不存在sourceprovider标签，则添加
        if not sourceprovider_exists:
            sourceprovider = etree.Element("sourceprovider")
            sourceprovider.text = "IqiyiID"
            # 将sourceprovider标签插入到根元素的开头
            root.insert(0, sourceprovider)
            modified = True
            # logger.info(f"✅ 添加sourceprovider标签: IqiyiID in {filepath}")
        
        # 如果有修改，保存文件并重命名
        if modified:
            # 构造新的文件名
            dir_path = os.path.dirname(filepath)
            filename = os.path.basename(filepath)
            name, ext = os.path.splitext(filename)
            new_filename = f"{name}_IqiyiID{ext}"
            new_filepath = os.path.join(dir_path, new_filename)
            
            # 检查新文件名是否已存在
            if os.path.exists(new_filepath):
                # 如果新文件名已存在，保存到原文件
                tree.write(filepath, encoding="utf-8", xml_declaration=True, pretty_print=True)
                # logger.info(f"💾 文件已保存(未重命名，目标文件已存在): {filepath}")
            else:
                # 保存到新文件名
                tree.write(new_filepath, encoding="utf-8", xml_declaration=True, pretty_print=True)
                # 删除原文件
                os.remove(filepath)
                # logger.info(f"💾 文件已保存并重命名: {filepath} -> {new_filepath}")
            return True
        else:
            # logger.info(f"⏩ 文件已符合要求: {filepath}")
            return False
            
    except etree.XMLSyntaxError as e:
        return ('error', f"XML语法错误: {e} | 可能原因: XML结构不完整或格式错误")
    except Exception as e:
        return ('error', f"处理失败: {type(e).__name__}: {e}")

def process_directory(directory):
    """
    处理指定目录下的所有XML文件
    返回处理的文件数量
    """
    if not os.path.exists(directory):
        raise Exception(f"目录不存在: {directory}")
    
    count = 0
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith('.xml'):
                filepath = os.path.join(root, file)
                try:
                    result = modify_xml(filepath)
                    if result is True:
                        count += 1
                    elif isinstance(result, tuple) and result[0] == 'error':
                        print(f"处理文件失败: {filepath}, 错误: {result[1]}")
                except Exception as e:
                    print(f"处理文件失败: {filepath}, 错误: {e}")
    
    return count

def create_test_xml(filepath, body_type="text"):
    """
    创建测试用的XML文件
    """
    xml_content = f'''<?xml version="1.0" encoding="utf-8"?>
<root>
    <body type="{body_type}">
        <p>这是一个测试字幕文件</p>
        <p>用于测试XML属性修改功能</p>
        <p>当前body type="{body_type}"</p>
    </body>
</root>'''
    
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(xml_content)
    
    print(f"📝 创建测试文件: {filepath}")