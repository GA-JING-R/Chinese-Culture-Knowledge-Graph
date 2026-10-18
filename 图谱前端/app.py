# -*- coding: utf-8 -*-
from flask import Flask, render_template, jsonify, request
from py2neo.errors import ConnectionUnavailable
from neo4j_db import (
    test_connection, get_all_nodes, get_all_relationships,
    search_nodes, get_node_detail, get_shortest_path,
    get_statistics, get_nodes_by_category, get_graph_data
)

app = Flask(__name__)


@app.errorhandler(ConnectionUnavailable)
def handle_db_unavailable(error):
    """数据库未启动时返回友好提示，避免整个页面报 500"""
    return jsonify({
        "error": "数据库连接不可用：请确认 Neo4j 已启动（bolt://localhost:7687）"
    }), 503

@app.route('/')
def index():
    """首页"""
    return render_template('index.html')

@app.route('/api/status')
def status():
    """API: 检查数据库连接状态"""
    return jsonify(test_connection())

@app.route('/api/statistics')
def statistics():
    """API: 获取统计信息"""
    return jsonify(get_statistics())

@app.route('/api/graph')
def graph_data():
    """API: 一次性获取整张图谱（节点 + 关系），供前端渲染"""
    return jsonify(get_graph_data())

@app.route('/api/nodes')
def nodes():
    """API: 获取所有节点"""
    return jsonify(get_all_nodes())

@app.route('/api/nodes/category/<category>')
def nodes_by_category(category):
    """API: 按类别获取节点"""
    return jsonify(get_nodes_by_category(category))

@app.route('/api/relationships')
def relationships():
    """API: 获取所有关系（用于图谱）"""
    return jsonify(get_all_relationships())

@app.route('/api/search')
def search():
    """API: 搜索节点"""
    keyword = request.args.get('q', '')
    if not keyword:
        return jsonify([])
    return jsonify(search_nodes(keyword))

@app.route('/api/node/<path:node_name>')
def node_detail(node_name):
    """API: 获取节点详情"""
    detail = get_node_detail(node_name)
    if detail:
        return jsonify(detail)
    return jsonify({"error": "节点不存在"}), 404

@app.route('/api/path')
def path():
    """API: 查找两个节点之间的路径"""
    source = request.args.get('source', '')
    target = request.args.get('target', '')
    if not source or not target:
        return jsonify({"error": "请提供 source 和 target 参数"}), 400
    return jsonify(get_shortest_path(source, target))

@app.route('/api/recommend/<person_name>')
def recommend(person_name):
    """相似人物推荐API"""
    from neo4j_db import recommend_similar_person
    recommendations = recommend_similar_person(person_name)
    # 确保返回的是数组
    if recommendations is None:
        recommendations = []
    return jsonify(recommendations)

# ==================== 问答系统 ====================

def parse_question(question):
    """
    NLU解析：从问题中提取实体和意图
    返回: (entity, intent)
    """
    import re
    
    # 定义人物列表
    persons = ['孔子', '李白', '杜甫', '司马迁', '苏轼', '王羲之', '白居易', '曹操', '颜回', '司马谈']
    
    # 提取实体（人物名）
    entity = None
    for person in persons:
        if person in question:
            entity = person
            break
    
    if not entity:
        return None, None
    
    # 识别意图
    intent = None
    if '朝代' in question or '生活在' in question or '哪个朝' in question:
        intent = 'dynasty'
    elif '出生' in question or '生于' in question or '哪里人' in question:
        intent = 'birthplace'
    elif '著作' in question or '作品' in question or '写了' in question or '创作' in question:
        intent = 'works'
    elif '朋友' in question or '好友' in question:
        intent = 'friend'
    elif '简介' in question or '介绍' in question or '是谁' in question:
        intent = 'intro'
    
    return entity, intent


def generate_answer(entity, intent, result):
    """
    答案融合：将查询结果转换为自然语言
    """
    if result is None:
        return f"抱歉，未找到关于「{entity}」的信息。"
    
    if intent == 'dynasty':
        return f"📜 {entity}生活在{result}。"
    
    elif intent == 'birthplace':
        return f"📍 {entity}出生于{result}。"
    
    elif intent == 'works':
        if isinstance(result, list):
            works_str = '、'.join(result)
            return f"📖 {entity}的作品有：{works_str}。"
        return f"📖 {entity}的作品有：{result}。"
    
    elif intent == 'friend':
        if isinstance(result, list) and len(result) > 0:
            friends_str = '、'.join(result)
            return f"👥 {entity}的朋友有：{friends_str}。"
        return f"👥 {entity}暂无朋友信息。"
    
    elif intent == 'intro':
        return f"ℹ️ {entity}：{result}"
    
    return f"关于「{entity}」的信息：{result}"


@app.route('/api/qa', methods=['POST'])
def qa():
    """
    问答系统API
    请求格式: {"question": "李白在哪个朝代？"}
    """
    data = request.get_json()
    question = data.get('question', '')
    
    if not question:
        return jsonify({"error": "请输入问题"}), 400
    
    # 流程1: NLU解析
    entity, intent = parse_question(question)
    
    if not entity:
        return jsonify({
            "question": question,
            "answer": "❓ 无法识别问题中的人物，请试试：孔子、李白、杜甫等"
        })
    
    if not intent:
        return jsonify({
            "question": question,
            "answer": f"❓ 无法理解您的问题，试试问：{entity}在哪个朝代？"
        })
    
    # 流程2: 查询Neo4j
    from neo4j_db import answer_question
    result = answer_question(entity, intent)
    
    # 流程3: 生成答案
    answer = generate_answer(entity, intent, result)
    
    return jsonify({
        "question": question,
        "answer": answer,
        "entity": entity,
        "intent": intent
    })

if __name__ == '__main__':
    print("=" * 60)
    print("🏛️ 汉文化知识图谱 Web 应用")
    print("📍 访问地址: http://localhost:5000")
    print("=" * 60)
    app.run(debug=True, host='0.0.0.0', port=5000)