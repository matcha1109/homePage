import os

from flask import Flask, render_template, session, redirect, request, url_for, flash, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from sqlalchemy.dialects.mysql import mysqldb
from werkzeug.utils import secure_filename
from wtforms import StringField, SubmitField, PasswordField, IntegerField, DateField, FileField
from wtforms.validators import DataRequired, length, EqualTo, Regexp, Email, NumberRange
from flask_bootstrap import Bootstrap
import pymysql
from swiftclient import Connection, ClientException
import netifaces

pymysql.install_as_MySQLdb()
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'static/upload/'
app.secret_key = 'aasd'
bootstrap = Bootstrap(app)
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://root:123456@127.0.0.1:3306/flask'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
conn = pymysql.connect(host="127.0.0.1", user="root", password="123456", database="flask")
cursor = conn.cursor()
OS_AUTH_URL = 'http://192.168.1.200:35357/v2.0'
OS_USERNAME = 'admin'
OS_TENANT_NAME = 'admin'
OS_PASSWORD = '000000'
swift_conn = Connection(
    authurl=OS_AUTH_URL,
    user=OS_USERNAME,
    key=OS_PASSWORD,
    auth_version=2,
    tenant_name=OS_TENANT_NAME
)


def Create_Container(user):
    container = user
    swift_conn.put_container(container)
    resp_headers, containers = swift_conn.get_account()
    for container in containers:
        print(container)


class Users(db.Model):
    __tablename__ = 'user'
    user_name = db.Column(db.String(8), primary_key=True)
    user_pwd = db.Column(db.String(200), nullable=False)
    user_mail = db.Column(db.String(20), unique=True)
    user_age = db.Column(db.Integer)


class Register(FlaskForm):
    name = StringField("用户名：", validators=[DataRequired(), length(3, 10, message="用户名字数3-10")])
    pwd1 = PasswordField("密码：", validators=[DataRequired(), length(3, 10, message="密码字数3-10")])
    pwd2 = PasswordField("确认密码：", validators=[DataRequired(), EqualTo('pwd1', message="密码不相同")])
    mail = StringField("邮箱：", validators=[DataRequired(), Email(message="邮箱错误")])
    age = IntegerField("年龄：", validators=[DataRequired(), NumberRange(1, 120, message="年龄范围1-120")])
    submit = SubmitField("注册")


class Login(FlaskForm):
    name = StringField("用户", validators=[DataRequired(), Email()])
    pwd = PasswordField("密码", validators=[DataRequired()])
    submit = SubmitField("登录")


# db.drop_all()
db.create_all()


@app.route('/', methods=['post', 'get'])
def Index():
    return render_template('index2.html')


@app.route('/register', methods=['post', 'get'])
def Register_index():
    register_value = Register()
    if register_value.validate_on_submit():
        #  登录页面的数据显示
        session['name'] = register_value.name.data
        session['pwd'] = register_value.pwd1.data
        #  数据库信息提交
        u_user = request.form.get('name', None)
        u_pwd = request.form.get('pwd2')
        u_mail = request.form.get('mail', None)
        u_age = request.form.get('age', None)
        sql = 'select * from user where user_name="%s"' % u_mail
        if cursor.execute(sql) > 0:
            conn.commit()
            flash('邮箱已存在')
            return redirect('/register')
        garbage_name = "garbage_%s" % u_user
        new_user = Users(user_name=u_user, user_pwd=u_pwd, user_mail=u_mail, user_age=u_age)
        db.session.add(new_user)
        db.session.commit()
        Create_Container(u_user)
        Create_Container(garbage_name)
        return redirect('/login')

    return render_template('register.html', register=register_value)


@app.route('/login', methods=['post', 'get'])
def Login_index():
    login = Login()
    if request.method == 'POST':
        l_mail = request.form.get('name')
        l_pwd = request.form.get('pwd')
        session['name'] = login.name.data
        session['pwd'] = login.pwd.data
        sql = 'select * from user where user_name="%s" and user_pwd="%s"' % (l_mail, l_pwd)
        conn.commit()
        cursor.execute(sql)
        data = cursor.fetchone()
        if cursor.execute(sql) > 0:
            flash(data[0])
            return redirect('/cloud')
        else:
            flash('邮箱不存在或密码错误')
            return redirect('/login')

    return render_template('login.html', login1=login)


# @app.route('/welcome', methods=['post', 'get'])
# def Welcome():
#     sql = 'select * from user'
#     conn.commit()
#     cursor.execute(sql)
#     data = cursor.fetchall()
#
#     return render_template('welcome.html', data=data)


@app.route('/cloud', methods=['POST', 'GET'])
def welcome():
    print(request.args.get("path"))
    username = session.get("name")
    if username is None:
        return redirect('/login')

    currentPath = request.args.get("path")

    if currentPath == None:
        resp_headers, filelist = swift_conn.get_container(container=username)
        currentFilelist = []
        for file in filelist:
            index = file.get('name').find('/' )
            if index == -1 or index == len(file.get('name')) - 1:
                currentFilelist.append(file)
        filelist = currentFilelist
    else:
        resp_headers, filelist = swift_conn.get_container(container=username, path=currentPath)
    return render_template('filelist.html', filelist=filelist)


@app.route('/upload', methods=['POST', 'GET'])
def upload():
    username = session.get('name')
    if username == None:
        return redirect('/login')
    f = request.files['file']
    currentPath = str(request.args.get('path'))
    if currentPath == 'None':
        currentPath = ''
    f.save('static/upload/' + f.filename)
    with open('static/upload/' + f.filename, 'rb') as local:
        swift_conn.put_object(username, currentPath + f.filename, contents=local, content_type='text/plain')
    return redirect('/cloud')


@app.route('/download')
def download():
    username = session.get('name')
    if username == None:
        return redirect('/login')
    currentPath = str(request.args.get('path'))
    resp_headers, obj_contents = swift_conn.get_object(container=username, obj=currentPath)
    index = currentPath.rfind('/')
    currentPath = currentPath[index + 1:len(currentPath)]
    print(currentPath)
    with open('static/' + currentPath, 'wb') as local:
        local.write(obj_contents)
    return send_from_directory('static/', currentPath, attachment_filename=currentPath, as_attachment=True)


@app.route('/delete')
def delete():
    username = session.get('name')
    if username == None:
        return redirect('/login')
    filename = request.args.get('filename')
    swift_conn.copy_object(container=username, obj=filename, destination='garbage_' + username + '/' + filename)
    swift_conn.delete_object(container=username, obj=filename)
    return redirect('/cloud')


@app.route('/logout')
def logout():
    session.clear()
    return redirect("login")


@app.route('/mkdir', methods=['POST'])
def mkdir():
    username = session.get("name")
    # 获得文件夹名称信息
    dirname = request.form.get("dirname")
    path = request.form.get("path")
    currentPath = str(request.args.get('path'))
    if currentPath == 'None':
        currentPath = ''
    swift_conn.put_object(username, currentPath + dirname, contents=None, content_type='text/directory')
    return redirect('/cloud' + currentPath)


@app.route('/garbage', methods=['POST', 'GET'])
def garbage():
    print(request.args.get("path"))
    username = session.get("name")
    resp_headers, filelist = swift_conn.get_container(container='garbage_' + username)
    return render_template('garbagefile.html', filelist=filelist)


@app.route('/delete_garbage')
def delete_garbage():
    username = session.get('name')
    if username == None:
        return redirect('/login')
    filename = request.args.get('filename')
    swift_conn.delete_object(container='garbage_' + username, obj=filename)
    return redirect('/garbage')


@app.route('/restore')
def restore():
    username = session.get('name')
    if username == None:
        return redirect('/login')
    filename = request.args.get('filename')
    swift_conn.copy_object(container='garbage_' + username, obj=filename,
                           destination=username + '/' + filename)
    swift_conn.delete_object(container='garbage_' + username, obj=filename)
    return redirect('/garbage')


if __name__ == '__main__':
    app.run()
    cursor.close()
    conn.close()
