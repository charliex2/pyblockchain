from time import time
import json
import hashlib
from textwrap import dedent
from uuid import uuid4
from flask import Flask, jsonify, request
from urllib.parse import urlparse
import requests


class BlockChain(object):
    def __init__(self):
        self.chain = []
        self.current_transactions = []

        # 相邻的节点
        self.nodes = set()

        # 创建创世区块
        self.new_block(previous_hash=1, proof=100)

    def new_block(self, proof, previous_hash=None):
        # create a new block and add it to chain
        """
        创建一个新的区块到区块链
        :param proof:<int> 由工作证明算法生成的证明
        :param previous_hash:(Optional) <str> 前一个区块的hash值
        :return:<dict> 区块链
        """
        block = {
            'index': len(self.chain) + 1,
            'timestamp': time(),
            'transactions': self.current_transactions,
            'proof': proof,
            'previous_hash': previous_hash or self.hash(self.chain[-1])
        }

        # 重置当前交易记录
        self.current_transactions = []
        self.chain.append(block)
        return block

    def new_transaction(self, sender, recipient, amount):
        """
        Create a new transaction to go into next mined Block
        :param sender:<string> 发送者的地址
        :param recipient:<string> 接收者的地址
        :param amount: 数量
        :return:<int> The index of the Block that will hold this transaction
        """
        self.current_transactions.append({
            'sender': sender,
            'recipient': recipient,
            'amount': amount
        })

        # 返回来交易将要被添加到的区块的索引
        return self.last_block['index'] + 1

    @staticmethod
    def hash(block):
        """
        给一个区块生成SHA-256
        :param block: <dict> Block
        :return: <str>
        """

        # 我们必须确保这个字典(区块）是进过排序的，否则我们将会得到不一致的散列

        block_string = json.dumps(block, sort_keys=True).encode()
        return hashlib.sha256(block_string).hexdigest()

    @property
    def last_block(self):
        # return last block in the chain
        return self.chain[-1]

    def proof_of_work(self, last_proof):
        """
        实现一个简单的工作证明算法
        找到一个数字P，使得它与前一个区块的proof拼接而成的字符串的Hash值以4个0开头
        :param last_proof:<int>
        :return:<int>
        """
        proof = 0
        while self.valid_proof(last_proof, proof) is False:
            proof += 1
        return proof

    @staticmethod
    def valid_proof(last_proof, proof):
        """
        校验hash
        :param last_proof:
        :param proof:
        :return:
        """
        guess = f'{last_proof}{proof}'.encode()
        guess_hash = hashlib.sha256(guess).hexdigest()
        return guess_hash[:4] == "0000"

    def register_node(self, address):
        """
        Add a node to the list of nodes
        :param address:
        :return:
        """
        parsed_url = urlparse(address)
        self.nodes.add(parsed_url.netloc)

    def valid_chain(self, chain):
        """
        判断一个区块链是否合法
        :param chain:<list>
        :return:<bool>
        """

        last_block = chain[0]
        current_index = 1

        while current_index < len(chain):
            block = chain[current_index]

            if block['previous_hash'] != self.hash(block):
                return False

            if not self.valid_proof(last_block['proof'], block['proof']):
                return False

            last_block = block
            current_index += 1

        return True

    def resolve_conflicts(self):
        """
        在所有的节点中找到一条最长的链
        :return:<bool>
        """
        neighbours = self.nodes
        new_chain = None

        max_length = len(self.chain)

        for node in neighbours:
            respones = requests.get(f'http://{node}/chain')
            if respones.status_code == 200:
                length = respones.json()["length"]
                chain = respones.json()["chain"]
                if length > max_length and self.valid_chain(chain):
                    max_length = length
                    new_chain = chain
        if new_chain:
            self.chain = new_chain
            return True
        return False


# Instant our Node
app = Flask(__name__)

# 为该节点生成一个全球统一地址
node_identifier = str(uuid4()).replace('-', '')

# 实例化区块链
blockchain = BlockChain()


@app.route('/mine', methods=['GET'])
def mine():
    # 运行工作证明算法得到下一个工作证明
    last_block = blockchain.last_block
    last_proof = last_block['proof']
    proof = blockchain.proof_of_work(last_block)

    # 找到一个工作证明，则收到一个新的coin奖励
    # 该奖励的发送者是 "0"
    blockchain.new_transaction(
        sender="0",
        recipient=node_identifier,
        amount=1,
    )

    # 锻造一个新的区块并且添加到区块链中去

    previous_hash = blockchain.hash(last_block)
    block = blockchain.new_block(proof, previous_hash)

    response = {
        "message": "New Block Forged",
        'index': block['index'],
        'transactions': block['transactions'],
        'proof': block['proof'],
        'previous_hash': block['previous_hash'],
    }

    return jsonify(response), 200


@app.route('/transactions/new', methods=['POST'])
def new_transactions():
    values = request.get_json()

    # Check that the  required fields are in the POST'ed data
    required = ['sender', 'recipient', 'amount']
    if not all(k in values for k in required):
        return "Missing values", 400

    # 创建新的交易(Transaction)
    index = blockchain.new_transaction(values['sender'], values['recipienr'], values['amount'])
    response = {'message': f'Transcation will be added to Block {index}'}
    return jsonify(response), 201


@app.route('/chain', methods=['GET'])
def full_chain():
    response = {
        'chain': blockchain.chain,
        'length': len(blockchain.chain)
    }
    return jsonify(response), 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
