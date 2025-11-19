from peewee import *
from config import Config

db = MySQLDatabase(
    Config.mysql_db,
    user=Config.mysql_user,
    password=Config.mysql_password,
    host=Config.mysql_host,
    port=Config.mysql_port,
    charset='utf8mb4'
)

class BaseModel(Model):
    class Meta:
        database = db

class ConfidraMudiri(BaseModel):
    id = AutoField()
    full_name = CharField(max_length=255)
    image = CharField(max_length=500)
    description = TextField(null=True)
    facultet_type = IntegerField()

    class Meta:
        table_name = "confidra_mudiri"
        indexes = (
            (('facultet_type',), False),
        )

class User(BaseModel):
    id = AutoField()
    telegram_id = BigIntegerField(unique=True)
    first_name = CharField(max_length=100, null=True)
    last_name = CharField(max_length=100, null=True)
    lang = CharField(max_length=10, default="uz")
    
    confedra_mudiri = ForeignKeyField(
        ConfidraMudiri,
        backref='votes',
        null=True,
        on_delete='SET NULL'
    )

    class Meta:
        table_name = "users"
        indexes = (
            (('confedra_mudiri',), False),
        )