from time import sleep
from json import dumps, loads
from random import choice, random, randrange

from requests import get, post
from requests.utils import add_dict_to_cookiejar


from cli import UIPrinter, Fore, Back, Style

AUTHCODE = '将这个内容替换为您的Cookie里__jsluid_h=后面的内容'

headers={
	'Cookies': f'__jsluid_h={AUTHCODE}',
	'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.116 Safari/537.36'
}

class Application(UIPrinter):
	def main(self):
		self.wait('正在生成个人信息...')
		name, gender = self.generate_name()
		hos = '他' if gender else '她' # He or She
		pname, pgender = self.generate_name()
		pgender = '父' if pgender else '母'
		self.note(f'{hos}叫{name} {pgender}亲叫{pname}')
		did, dname = self.generate_district()
		self.note(f'{hos}住在{dname}(区ID:{did})')
		ograde, grade, sgrade, gname, stype = self.generate_grade()
		stype_name = {
			1: '小学',
			2: '初中',
			3: '高中',
			4: '幼儿园'
		}[stype]
		self.note(f'{hos}读{stype_name}(学校类型ID:{stype}){sgrade}(年级ID:{ograde})')
		sclass = self.generate_class()
		self.note(f'{hos}在{sclass} 参加{gname}(组别ID:{grade})')
		schid, sname = self.generate_school(did, stype)
		self.note(f'{hos}就读的学校是{sname}(学校ID:{schid})')
		gender = 1 if gender else 2
		sid = self.get_student_id()
		self.note(f'{hos}的用户ID是 {sid}')
		regcode = self.get_reg_code()
		self.note(f'{hos}的注册码是 {Fore.LIGHTWHITE_EX}{Back.LIGHTBLACK_EX}{regcode}{Style.RESET_ALL}')
		try:
			self.register(sid, name, gender, pname, pgender, did, dname, schid, sname, sgrade, grade, gname, sclass, regcode)
		except RegisterFailure:
			self.fail('注册失败 未知原因')
		self.succ(f'注册成功')
		try:
			token = self.login(regcode, self.PASSWORD)
		except LoginPasswordUnmatch:
			self.fail(f'登录失败 密码错误(尝试的密码: {self.PASSWORD})')
		except LoginUserNotFound:
			self.fail('登录失败 找不到用户')
		self.succ(f'登录成功 {token}')
		rows = self.load_question_entites(token, grade, schid, gender)['Rows']
		self.succ(f'已拿到试卷 共{len(rows)}道题')
		answer_rows = []
		# Fill in right answers
		for row in rows:
			answer_rows.append({
				'TestPageId': row['TestPaperId'],
				'TestQuestionId': row['Id'],
				'Code': row['Code'],
				'Answer': row['AnswerRight'],
				'AnswerRight': {
					'A': 1,
					'B': 2,
					'C': 3,
					'D': 4,
					'E': 5, # Just in case
					'F': 6
				}[row['AnswerRight']]
			})
		self.succ(f'根据正确答案 已生成全对的试卷')
		ret = int(self.add_offical_test_extend(token, sid, grade, answer_rows))
		if ret == 0:
			self.warn(f'没有证书')
		elif ret <= 0:
			self.fail(f'提交时发生错误 返回值: {ret}')
		else:
			self.succ(f'已交卷 {Back.LIGHTGREEN_EX}{Fore.BLACK}答题时间: {self.TESTTIME}秒{Style.RESET_ALL}')
		ranking = self.rank(token, sid, grade)
		self.note(f'{Fore.LIGHTGREEN_EX}全上海{Style.RESET_ALL}{gname}排名: {Fore.LIGHTGREEN_EX}第{ranking}名{Style.RESET_ALL}')
	def register(self, sid, name, gender, pname, pgender, did, dname, schid, sname, sgrade, grade, gname, sclass, regcode):
		form = {
			'EntityName': 'RStudent',
			'Rows': [{'Id': sid,
					  'Name': name,
					  'DistrictId': did,
					  'DistrictName': dname,
					  'SchoolId': schid,
					  'SchoolName': sname,
					  'StudentGrade': sgrade,
					  'Grade': grade,
					  'GradeName': gname,
					  'StudentClass': sclass,
					  'RegCode': regcode,
					  'Password': self.PASSWORD,
					  'ProtectQuestion': f'您{pgender}亲的姓名是？',
					  'ProtectAnswer': pname,
					  'Type': 1,
					  'Sex': gender,
					  'Email': '',
					  'RecordState': 1,
					  'ActivityId': 1005
					  }], 'Total': 1
		}
		if not self.save_student_entities(form):
			raise RegisterFailure()
		return regcode, schid, gender
	def login(self, regcode, password):
		ret = self.user_login_student(regcode, password)
		if ret['Code'] == 1:
			raise LoginUserNotFound()
		elif ret['Code'] == 2:
			raise LoginPasswordUnmatch()
		else:
			return ret['Token']
	def rank(self, token, sid, grade):
		sql = f'SELECT t.rid AS Ranking FROM ( SELECT a.StudentId, ROW_NUMBER ( ) OVER ( ORDER BY a.TopScore DESC, a.TestTime ) AS rid FROM tb_OfficialTest a WHERE a.ActivityId = 1005 AND a.Grade = {grade} ) t WHERE t.StudentId = {sid}'
		ret = self.load_entites(token, sql)
		if 'Code' in ret:
			self.fail(f"查询排名时出错 错误码: {ret['Code']}")
		else:
			return ret['Rows'][0]['Ranking']
	def generate_district(self):
		districts = self.load_district_entities()['Rows']
		district = choice(districts)
		return district['Id'], district['Name']
	def generate_class(self):
		classes = self.load_dictionary_entites("GroupTitle='班级' order by ItemValue")['Rows']
		_class = choice(classes)
		return _class['ItemName']
	def generate_grade(self):
		grade = randrange(1, 16)
		student_grade = {
			1: '一年级',
			2: '二年级',
			3: '三年级',
			4: '四年级',
			5: '五年级',
			6: '六年级',
			7: '初一年级',
			8: '初二年级',
			9: '初三年级',
			10: '高一(中职校一年级)',
			11: '高二(中职校二年级)',
			12: '高三(中职校三年级)',
			13: '小班',
			14: '中班',
			15: '大班'
		}[grade]
		school_type, api_grade, grade_name = {
			grade <= 3: (1, 1, '小学低年级组'),
			grade == 4 or grade == 5: (1, 2, '小学高年级组'),
			grade >= 6 and grade <= 9: (2, 3, '初中组'),
			grade >= 10 and grade <= 12: (3, 4, '高中组'),
			grade >= 13 and grade <= 15: (4, 1, '小学低年级组') # 幼儿园
		}[True]
		if not student_grade or not grade_name:
			raise DefaultError()
		return grade, api_grade, student_grade, grade_name, school_type
	def generate_school(self, did, stype):
		schools = self.load_school_entites(did, stype)['Rows']
		school = choice(schools)
		schid = school['Id']
		sname = school['Name']
		return schid, sname
	def generate_name(self):
		# https://blog.csdn.net/qq_39208536/java/article/details/79624884
		first_names='赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦尤许何吕施张孔曹严华金魏陶姜'
		boy_last_names='涛昌进林有坚和彪博诚先敬震振壮会群豪心邦承乐绍功松善厚庆磊民友裕河哲江超浩亮政谦亨奇固之轮翰朗伯宏言若鸣朋斌梁栋维启克伦翔旭鹏泽晨辰士以建家致树炎德行时泰盛雄琛钧冠策腾伟刚勇毅俊峰强军平保东文辉力明永健世广志义兴良海山仁波宁贵福生龙元全国胜学祥才发成康星光天达安岩中茂武新利清飞彬富顺信子杰楠榕风航弘'
		girl_last_names='嘉琼桂娣叶璧璐娅琦晶妍茜秋珊莎锦黛青倩婷姣婉娴瑾颖露瑶怡婵雁蓓纨仪荷丹蓉眉君琴蕊薇菁梦岚苑婕馨瑗琰韵融园艺咏卿聪澜纯毓悦昭冰爽琬茗羽希宁欣飘育滢馥筠柔竹霭凝晓欢霄枫芸菲寒伊亚宜可姬舒影荔枝思丽秀娟英华慧巧美娜静淑惠珠翠雅芝玉萍红娥玲芬芳燕彩春菊勤珍贞莉兰凤洁梅琳素云莲真环雪荣爱妹霞香月莺媛艳瑞凡佳'
		first_name=choice(first_names)
		gender=random() > 0.5
		last_name="".join(
			choice(boy_last_names if gender else girl_last_names) for i in range(2))
		return (first_name + last_name), gender
	def convert(self, size):
		'''转换为人类可读单位'''
		# https://blog.csdn.net/mp624183768/article/details/84892999
		kb = 1024
		mb = 1024 * 1024
		gb = 1024 * 1024 * 1024
		tb = 1024 * 1024 * 1024 * 1024
		if size >= tb:
			return '%.1f TB' % (size / tb)
		elif size >= gb:
			return '%.1f GB' % (size / gb)
		elif size >= mb:
			return '%.1f MB' % (size / mb)
		elif size >= kb:
			return '%.1f KB' % (size / kb)
		else:
			return '%d B' % size
	def get_reg_code(self):
		'''str注册码'''
		return self.req('getStudentRegCode')
	def get_student_id(self):
		'''int用户id'''
		return int(self.req('getStudentId'))
	def save_student_entities(self, entities):
		'''False 出错'''
		return self.req('saveStudentEntities', {'entities': dumps(entities)}) == '0'
	def user_login_student(self, username, password):
		return loads(self.req('userLoginStudent', {'username': username, 'password': password}))
	def load_entites(self, token, candition):
		return loads(self.req('loadEntites', {
			'signature': token,
			'entityClassName': 'RDataset',
			'candition': candition
		}))
	def load_dictionary_entites(self, candition):
		return loads(self.req('loadDictionaryEntites', {'candition': candition}))
	def load_question_entites(self, token, grade, schid, gender):
		return loads(self.req('loadQuestionEntites', {
			'signature': token,
			'activityId': 1005,
			'grade': grade,
			'schoolId': schid,
			'studentType': 1,
			'sex': gender
		}))
	def load_school_entites(self, did, stype):
		return loads(self.req('loadSchoolEntitesByCache', {'candition': dumps({'DistrictId': did, 'ItemType': stype})}))
	def load_district_entities(self):
		return loads(self.req('loadDistrictEntitesByCache', {'candition': {}}))
	def add_offical_test_extend(self, token, sid, grade, rows):
		return self.req('addOfficialTestExtend', {
			'row': dumps({
				'TestTime': self.TESTTIME,
				'StudentId': sid,
				'Score': 100,
				'Grade': grade,
				'ActivityId': 1005,
				'Type': 1
			}),
			'officialTestDetial': dumps({
				'EntityName': 'ROfficialTestDetial',
				'Rows': rows,
				'Total': 0
			}),
			'signature': token
		})
	def req(self, service, data = None):
		res = post('http://wsjy1.secsa.cn/contestClient/services/ContestService/' + service, data = data, headers = headers)
		cookies = res.headers.get('Set-Cookies')
		if cookies:
			headers['Cookies'] = cookies + ';' + headers['Cookies']
			self.warn(f'已加入 Cookie {cookies}')
		return res.text
	def __init__(self):
		UIPrinter.__init__(self, 'SECSA')

class DefaultError(Exception):
	'''不满足任一条件'''

class RegisterFailure(Exception):
	'''注册失败 返回值非零 ID!=0'''

class LoginUserNotFound(Exception):
	'''登录失败 找不到用户 ID=1'''

class LoginPasswordUnmatch(Exception):
	'''登录失败 密码错误 ID=2'''

if __name__ == '__main__':
	app = Application()
	if AUTHCODE == '将这个内容替换为您的Cookie里__jsluid_h=后面的内容':
		app.fail('请打开本脚本源码 并将AUTHCODE的内容替换为您的Cookie')
	app.ask(f'注册密码: {Fore.LIGHTYELLOW_EX}{Back.LIGHTYELLOW_EX}')
	app.PASSWORD = input()
	print(f'{Style.RESET_ALL}', end='')
	app.ask('答题时间: ')
	app.TESTTIME = int(input())
	while True:
		app.main()