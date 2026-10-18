# -*- coding: utf-8 -*-
"""
任务4：将汉文化三元组 CSV 导入 Neo4j（修正版）
"""

import pandas as pd
from py2neo import Graph, Node, Relationship

# ==================== 1. 连接 Neo4j ====================
print("=" * 60)
print("任务4：汉文化知识图谱 - CSV导入Neo4j")
print("=" * 60)

# 连接数据库（请修改密码为你的实际密码）
# 尝试常见密码：Today1007, 12345678, neo4j
graph = Graph("bolt://localhost:7687", auth=("neo4j", "12345678"))

# 测试连接
try:
    graph.run("RETURN 1").data()
    print("✅ Neo4j 连接成功！")
except Exception as e:
    print(f"❌ 连接失败：{e}")
    print("请检查：1. Neo4j是否运行 2. 密码是否正确")
    exit()

# ==================== 2. 读取三元组 CSV ====================
print("\n>> 读取三元组文件...")
df = pd.read_csv("han_culture_triples.csv", encoding="utf-8-sig")
print(f"✅ 读取到 {len(df)} 条三元组")

print(f"\n列名：{df.columns.tolist()}")
print(f"\n前5条数据：")
print(df.head())

# ==================== 3. 清空旧数据（可选）====================
confirm = input("\n是否清空原有数据？(y/n): ")
if confirm.lower() == 'y':
    graph.run("MATCH (n) DETACH DELETE n")
    print("✅ 已清空数据库")

# ==================== 4. 创建节点和关系 ====================
print("\n>> 开始创建节点和关系...")

# 用于缓存已创建的节点，避免重复创建
nodes_cache = {}

def get_or_create_node(label, name):
    """获取或创建节点"""
    cache_key = f"{label}_{name}"
    
    if cache_key in nodes_cache:
        return nodes_cache[cache_key]
    
    # 查找是否已存在
    matcher = graph.nodes.match(label, name=name)
    existing = matcher.first()
    
    if existing:
        nodes_cache[cache_key] = existing
        return existing
    
    # 创建新节点
    node = Node(label, name=name)
    graph.create(node)
    nodes_cache[cache_key] = node
    return node

# 遍历每一行三元组
created_count = 0
for idx, row in df.iterrows():
    # 注意：列名是 subject, predicate, object, object_type
    subject_name = row['subject']      # 头实体（人物）
    predicate = row['predicate']       # 关系
    object_name = row['object']        # 尾实体
    object_type = row['object_type']   # 尾实体类型（Dynasty/Work/Location/Person）
    
    # 头实体节点（类型 Person，因为头实体都是人物）
    subject_node = get_or_create_node("Person", subject_name)
    
    # 尾实体节点（根据尾实体类型创建）
    object_node = get_or_create_node(object_type, object_name)
    
    # 创建关系
    relationship = Relationship(subject_node, predicate, object_node)
    graph.create(relationship)
    
    created_count += 1
    if (idx + 1) % 10 == 0 or (idx + 1) == len(df):
        print(f"  已处理 {idx + 1}/{len(df)} 条")

print(f"\n✅ 共创建 {created_count} 条关系")

# ==================== 5. 创建索引（提升查询性能）====================
print("\n>> 创建索引...")
try:
    graph.run("CREATE INDEX IF NOT EXISTS FOR (p:Person) ON (p.name)")
    graph.run("CREATE INDEX IF NOT EXISTS FOR (d:Dynasty) ON (d.name)")
    graph.run("CREATE INDEX IF NOT EXISTS FOR (w:Work) ON (w.name)")
    graph.run("CREATE INDEX IF NOT EXISTS FOR (l:Location) ON (l.name)")
    print("✅ 索引创建完成")
except Exception as e:
    print(f"⚠️ 索引创建失败：{e}")

# ==================== 6. 统计信息 ====================
print("\n" + "=" * 60)
print("任务4执行完成！")

# 查询统计
result = graph.run("MATCH (n) RETURN labels(n) as label, count(n) as count")
print("\n节点统计：")
for record in result:
    labels = record['label']
    label_name = labels[0] if labels else "Unknown"
    print(f"  {label_name}: {record['count']}")

result = graph.run("MATCH ()-[r]->() RETURN type(r) as rel, count(r) as count")
print("\n关系统计：")
for record in result:
    print(f"  {record['rel']}: {record['count']}")

print("\n" + "=" * 60)
print("✅ 数据导入完成！")
print("\n请在 Neo4j Browser 中执行以下查询：")
print("  MATCH (n) RETURN n LIMIT 50")
print("  MATCH (n)-[r]->(m) RETURN n, r, m LIMIT 30")