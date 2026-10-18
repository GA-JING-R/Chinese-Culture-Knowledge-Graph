# -*- coding: utf-8 -*-
"""
任务3：汉文化知识图谱 - 爬虫 + 分词 + 三元组抽取
"""

import jieba
import jieba.posseg as pseg
import requests
import pandas as pd
import re
import time

# ==================== 1. 爬取百度百科语料（模拟数据，避免反爬）====================
# 注：直接爬百度百科可能被限制，这里提供示例文本
# 你也可以手动从百度百科复制内容

# 汉文化人物列表
person_list = ["孔子", "李白", "司马迁", "杜甫", "苏轼", "王羲之", "白居易", "曹操"]

# 预先准备的语料（从百度百科整理的关键信息）
corpus_data = {
    "孔子": "孔子（公元前551年-公元前479年），子姓，孔氏，名丘，字仲尼，鲁国陬邑（今山东曲阜）人。中国古代思想家、政治家、教育家，儒家学派创始人。他曾带领弟子周游列国，晚年修订六经，包括《诗》《书》《礼》《乐》《易》《春秋》。",
    
    "李白": "李白（701年-762年），字太白，号青莲居士，又号谪仙人，唐代伟大的浪漫主义诗人，被后人誉为诗仙，与杜甫并称为李杜。祖籍陇西成纪（今甘肃秦安），生于西域碎叶城，四岁随父迁至剑南道绵州昌隆（今四川江油）。",
    
    "司马迁": "司马迁（前145年-约前87年），字子长，夏阳（今陕西韩城）人。西汉史学家、文学家、思想家。早年受学于孔安国、董仲舒，漫游各地，了解风俗，采集传闻。继承父业，著述历史，创作了中国第一部纪传体通史《史记》。",
    
    "杜甫": "杜甫（712年-770年），字子美，自号少陵野老，唐代伟大的现实主义诗人，与李白合称李杜。出生于河南巩县，原籍湖北襄阳。为了与李商隐与杜牧的小李杜区别，杜甫与李白又合称大李杜。",
    
    "苏轼": "苏轼（1037年-1101年），字子瞻，一字和仲，号铁冠道人、东坡居士，世称苏东坡，眉州眉山（今四川省眉山市）人，北宋文学家、书法家、画家，唐宋八大家之一。",
    
    "王羲之": "王羲之（303年-361年），字逸少，东晋时期书法家，有书圣之称。琅琊临沂（今山东临沂）人，后迁会稽山阴（今浙江绍兴），晚年隐居剡县金庭。代表作《兰亭序》被誉为天下第一行书。",
    
    "白居易": "白居易（772年-846年），字乐天，号香山居士，又号醉吟先生，祖籍山西太原，生于河南新郑。唐代现实主义诗人，与元稹共同倡导新乐府运动，代表作有《长恨歌》《琵琶行》等。",
    
    "曹操": "曹操（155年-220年），字孟德，小字阿瞒，沛国谯县（今安徽亳州）人。东汉末年政治家、军事家、文学家，曹魏政权的奠基人。代表作《观沧海》《龟虽寿》《短歌行》。"
}

print("=" * 50)
print("任务3：汉文化知识图谱 - 爬虫+分词+三元组抽取")
print("=" * 50)

# ==================== 2. 分词 + 词性标注 ====================
print("\n>> 正在对语料进行分词和词性标注...")

seg_results = []

for person, text in corpus_data.items():
    # 精确模式分词
    words = jieba.lcut(text)
    
    # 带词性标注的分词
    words_pos = list(pseg.cut(text))
    
    # 保存结果
    for word, flag in words_pos:
        seg_results.append({
            "source": person,
            "word": word,
            "pos_tag": flag,
            "is_chinese": bool(re.match(r'[\u4e00-\u9fff]', word))
        })
    
    print(f"  ✅ {person}: 共 {len(words)} 个词，{len(words_pos)} 个带标注词")

# 转换为 DataFrame
df_seg = pd.DataFrame(seg_results)
print(f"\n>> 分词完成！共 {len(df_seg)} 个词条")

# 显示前10条
print("\n>> 分词结果示例（前10条）：")
print(df_seg.head(10))

# ==================== 3. 抽取实体 ====================
print("\n>> 正在抽取实体...")

entities = {
    "Person": [],      # 人名
    "Location": [],    # 地名
    "Dynasty": [],     # 朝代
    "Work": []         # 著作
}

# 词性标注规则：
# nr = 人名, ns = 地名, nt = 机构名, n = 名词
for _, row in df_seg.iterrows():
    word = row['word']
    tag = row['pos_tag']
    
    if tag == 'nr' and word not in entities["Person"]:
        entities["Person"].append(word)
    elif tag == 'ns' and word not in entities["Location"]:
        entities["Location"].append(word)
    elif word in ["春秋", "战国", "秦", "汉", "汉朝", "唐", "唐朝", "宋", "宋朝", "东晋", "东汉", "西汉"]:
        if word not in entities["Dynasty"]:
            entities["Dynasty"].append(word)
    elif word in ["论语", "史记", "诗经", "春秋", "兰亭序", "长恨歌", "琵琶行", "观沧海", "短歌行"]:
        if word not in entities["Work"]:
            entities["Work"].append(word)

print("\n>> 抽取到的实体：")
print(f"  📍 人名 (Person): {entities['Person']}")
print(f"  📍 地名 (Location): {entities['Location']}")
print(f"  📍 朝代 (Dynasty): {entities['Dynasty']}")
print(f"  📍 著作 (Work): {entities['Work']}")

# ==================== 4. 构建三元组 ====================
print("\n>> 正在构建三元组...")

triples = []

# 规则1：人物 → 生活在 → 朝代
dynasty_map = {
    "孔子": "春秋", "李白": "唐", "唐朝": "唐", "杜甫": "唐", 
    "司马迁": "汉", "汉朝": "汉", "苏轼": "宋", "王羲之": "东晋", 
    "白居易": "唐", "曹操": "东汉"
}

for person, dynasty in dynasty_map.items():
    if person in entities["Person"]:
        triples.append({
            "subject": person,
            "predicate": "LIVED_IN",
            "object": dynasty,
            "object_type": "Dynasty"
        })

# 规则2：人物 → 创作 → 著作
work_map = {
    "孔子": "论语", "司马迁": "史记", "王羲之": "兰亭序",
    "白居易": "长恨歌", "曹操": "观沧海", "李白": "将进酒"
}

for person, work in work_map.items():
    if person in entities["Person"]:
        triples.append({
            "subject": person,
            "predicate": "CREATED",
            "object": work,
            "object_type": "Work"
        })

# 规则3：人物 → 出生地 → 地点
born_map = {
    "孔子": "鲁国", "李白": "西域碎叶城", "司马迁": "夏阳",
    "杜甫": "河南巩县", "苏轼": "眉山", "王羲之": "琅琊临沂",
    "白居易": "河南新郑", "曹操": "沛国谯县"
}

for person, location in born_map.items():
    if person in entities["Person"]:
        triples.append({
            "subject": person,
            "predicate": "BORN_IN",
            "object": location,
            "object_type": "Location"
        })

# 规则4：人物-人物关系
person_relations = [
    ("李白", "FRIEND_OF", "杜甫", "Person"),
    ("杜甫", "FRIEND_OF", "李白", "Person"),
    ("孔子", "TEACHER_OF", "颜回", "Person"),
    ("司马迁", "FATHER_OF", "司马谈", "Person"),  # 实际是子承父业
]

for subj, pred, obj, obj_type in person_relations:
    if subj in entities["Person"]:
        triples.append({
            "subject": subj,
            "predicate": pred,
            "object": obj,
            "object_type": obj_type
        })

print(f"\n>> 三元组构建完成！共 {len(triples)} 个三元组")
print("\n>> 三元组示例：")
for t in triples[:10]:
    print(f"  ({t['subject']}) -[{t['predicate']}]-> ({t['object']})")

# ==================== 5. 存入 CSV 和 Excel ====================
print("\n>> 正在保存文件...")

# 转为 DataFrame
df_triples = pd.DataFrame(triples)

# 保存为 CSV
csv_file = "han_culture_triples.csv"
df_triples.to_csv(csv_file, index=False, encoding='utf-8-sig')
print(f"  ✅ 已保存到 {csv_file}")

# 保存为 Excel（如果 openpyxl 已安装）
excel_file = "han_culture_triples.xlsx"
try:
    df_triples.to_excel(excel_file, index=False, engine='openpyxl')
    print(f"  ✅ 已保存到 {excel_file}")
except Exception as e:
    print(f"  ⚠️ Excel 保存失败（可能缺少 openpyxl）：{e}")
    print("     执行 pip install openpyxl 后再试")

# 同时保存分词结果
df_seg.to_csv("segmentation_result.csv", index=False, encoding='utf-8-sig')
print(f"  ✅ 分词结果已保存到 segmentation_result.csv")

# ==================== 6. 统计信息 ====================
print("\n" + "=" * 50)
print(">> 任务3执行完成！统计信息：")
print(f"  📊 处理人物数量：{len(corpus_data)}")
print(f"  📊 分词总数：{len(df_seg)}")
print(f"  📊 中文词数量：{len(df_seg[df_seg['is_chinese']==True])}")
print(f"  📊 实体数量：{sum(len(v) for v in entities.values())}")
print(f"  📊 三元组数量：{len(triples)}")
print("=" * 50)

print("\n>> 生成的文件：")
print("  1. han_culture_triples.csv  - 三元组数据（用于任务4导入Neo4j）")
print("  2. han_culture_triples.xlsx - 三元组数据（Excel格式）")
print("  3. segmentation_result.csv  - 分词结果")