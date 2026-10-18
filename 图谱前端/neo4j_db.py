# -*- coding: utf-8 -*-
from py2neo import Graph

NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "12345678"  # 请修改你的密码


class _LazyGraph:
    """
    延迟连接：首次真正执行查询时才去连接数据库。

    这样即使 Neo4j 还没启动，Web 服务本身也能正常起来，
    页面会显示「数据库连接异常」的提示，而不是整个应用启动失败。
    """

    def __init__(self, uri, auth):
        self._uri = uri
        self._auth = auth
        self._graph = None

    def _connect(self):
        if self._graph is None:
            # 连接失败时抛异常且不缓存，下次查询会自动重试
            self._graph = Graph(self._uri, auth=self._auth)
        return self._graph

    def run(self, *args, **kwargs):
        return self._connect().run(*args, **kwargs)

    def __getattr__(self, name):
        return getattr(self._connect(), name)


graph = _LazyGraph(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

def test_connection():
    try:
        graph.run("RETURN 1 as num").data()
        return {"status": "success", "message": "连接成功"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def get_statistics():
    """获取统计信息"""
    stats = {}
    # 各类节点数量
    stats['total_nodes'] = graph.run("MATCH (n) RETURN count(n) as count").data()[0]['count']
    stats['total_relations'] = graph.run("MATCH ()-[r]->() RETURN count(r) as count").data()[0]['count']
    stats['persons'] = graph.run("MATCH (n:Person) RETURN count(n) as count").data()[0]['count']
    stats['dynasties'] = graph.run("MATCH (n:Dynasty) RETURN count(n) as count").data()[0]['count']
    stats['works'] = graph.run("MATCH (n:Work) RETURN count(n) as count").data()[0]['count']
    stats['locations'] = graph.run("MATCH (n:Location) RETURN count(n) as count").data()[0]['count']
    return stats

def get_nodes_by_category(category):
    """按类别获取节点"""
    query = f"MATCH (n:{category}) RETURN n.name as name ORDER BY n.name"
    return graph.run(query).data()

def get_all_nodes():
    query = "MATCH (n) RETURN n.name as name, labels(n)[0] as label"
    return graph.run(query).data()

def get_all_relationships():
    query = """
    MATCH (n)-[r]->(m)
    RETURN n.name as source, type(r) as relation, m.name as target,
           labels(n)[0] as source_type, labels(m)[0] as target_type
    """
    return graph.run(query).data()

def get_graph_data():
    """
    一次性取回整张图谱：节点（含类型与度数）+ 关系。
    前端据此直接渲染，无需在页面里硬编码任何节点名或坐标。
    """
    nodes = graph.run("""
    MATCH (n)
    OPTIONAL MATCH (n)-[r]-()
    RETURN n.name AS name, labels(n)[0] AS label, count(DISTINCT r) AS degree
    ORDER BY label, name
    """).data()
    links = get_all_relationships()
    return {"nodes": nodes, "links": links}


def search_nodes(keyword):
    query = """
    MATCH (n) WHERE n.name CONTAINS $keyword
    RETURN n.name as name, labels(n)[0] as label LIMIT 20
    """
    return graph.run(query, keyword=keyword).data()

def get_node_detail(node_name):
    query = """
    MATCH (n {name: $name})
    OPTIONAL MATCH (n)-[r]-(m)
    RETURN n.name as name, labels(n)[0] as label,
           collect(DISTINCT {relation: type(r), neighbor: m.name, neighbor_type: labels(m)[0]}) as relations
    """
    result = graph.run(query, name=node_name).data()
    return result[0] if result else None

def get_shortest_path(source, target):
    query = """
    MATCH p = shortestPath((start {name: $source})-[*..5]-(end {name: $target}))
    RETURN [node in nodes(p) | node.name] as path_nodes,
           [rel in relationships(p) | type(rel)] as path_relations
    """
    result = graph.run(query, source=source, target=target).data()
    return result[0] if result else None

# ==================== 相似人物推荐算法 ====================

def recommend_similar_person(person_name, limit=5):
    """
    相似人物推荐
    """
    results = []
    
    # 1. 同一朝代推荐
    query1 = """
    MATCH (p:Person {name: $name})-[:LIVED_IN]->(d:Dynasty)
    MATCH (other:Person)-[:LIVED_IN]->(d)
    WHERE other.name <> $name
    RETURN other.name as name, '生活在同一朝代' as reason
    LIMIT $limit
    """
    try:
        r1 = graph.run(query1, name=person_name, limit=limit).data()
        if r1:
            results.extend(r1)
    except Exception as e:
        print(f"查询1错误: {e}")
    
    # 2. 同一出生地推荐
    query2 = """
    MATCH (p:Person {name: $name})-[:BORN_IN]->(l:Location)
    MATCH (other:Person)-[:BORN_IN]->(l)
    WHERE other.name <> $name
    RETURN other.name as name, '出生地相同' as reason
    LIMIT $limit
    """
    try:
        r2 = graph.run(query2, name=person_name, limit=limit).data()
        if r2:
            results.extend(r2)
    except Exception as e:
        print(f"查询2错误: {e}")
    
    # 3. 共同朋友推荐
    query3 = """
    MATCH (p:Person {name: $name})-[:FRIEND_OF]-(common:Person)-[:FRIEND_OF]-(other:Person)
    WHERE other.name <> $name AND common.name <> $name
    RETURN other.name as name, '有共同朋友' as reason
    LIMIT $limit
    """
    try:
        r3 = graph.run(query3, name=person_name, limit=limit).data()
        if r3:
            results.extend(r3)
    except Exception as e:
        print(f"查询3错误: {e}")
    
    # 去重
    seen = set()
    unique_results = []
    for r in results:
        if r['name'] not in seen:
            seen.add(r['name'])
            unique_results.append(r)
    
    # 确保返回数组而不是 None
    return unique_results if unique_results else []

# ==================== 问答系统函数 ====================

def answer_question(entity, intent):
    """
    根据实体和意图查询Neo4j并返回答案
    """
    if intent == "dynasty":
        # 查询人物所在的朝代
        query = """
        MATCH (p:Person {name: $entity})-[:LIVED_IN]->(d:Dynasty)
        RETURN d.name as answer
        """
        result = graph.run(query, entity=entity).data()
        if result:
            return result[0]['answer']
        return None
    
    elif intent == "birthplace":
        # 查询人物的出生地
        query = """
        MATCH (p:Person {name: $entity})-[:BORN_IN]->(l:Location)
        RETURN l.name as answer
        """
        result = graph.run(query, entity=entity).data()
        if result:
            return result[0]['answer']
        return None
    
    elif intent == "works":
        # 查询人物的著作
        query = """
        MATCH (p:Person {name: $entity})-[:CREATED]->(w:Work)
        RETURN collect(w.name) as answer
        """
        result = graph.run(query, entity=entity).data()
        if result and result[0]['answer']:
            return result[0]['answer']
        return None
    
    elif intent == "friend":
        # 查询人物的朋友
        query = """
        MATCH (p:Person {name: $entity})-[:FRIEND_OF]-(f:Person)
        RETURN collect(f.name) as answer
        """
        result = graph.run(query, entity=entity).data()
        if result and result[0]['answer']:
            return result[0]['answer']
        return None
    
    elif intent == "intro":
        # 查询人物的简介
        query = """
        MATCH (p:Person {name: $entity})
        RETURN p.intro as answer
        """
        result = graph.run(query, entity=entity).data()
        if result and result[0]['answer']:
            return result[0]['answer']
        return None
    
    return None
