"""La cache del ORM sobrevive a un Environment() nuevo: es de la TRANSACCION."""
import django; django.setup()
import fields
from orm.environments import Environment
from orm.models import BaseModel

class P(BaseModel):
    _name = 'orm.leak.probe'
    _description = "Leak probe"
    label = fields.Char('Label')
    class Meta:
        app_label = 'base'; managed = False; db_table = 'orm_leak_probe'

campo = P._meta.get_field('label')
ids = (7, 18)

a = Environment()
rs_a = P._from_ids(a, ids, ids)
campo._insert_cache(rs_a, ['primero-7', 'primero-18'])
print('env A  ->', [r.label for r in rs_a])

b = Environment()
print('A is B                      :', a is b)
print('transaccion A is B          :', a.transaction is b.transaction)
rs_b = P._from_ids(b, ids, ids)
campo._insert_cache(rs_b, ['SEGUNDO-7', 'SEGUNDO-18'])
print('env B (tras _insert_cache)  ->', [r.label for r in rs_b])

b.invalidate_all()
rs_c = P._from_ids(b, ids, ids)
campo._insert_cache(rs_c, ['SEGUNDO-7', 'SEGUNDO-18'])
print('env B tras invalidate_all   ->', [r.label for r in rs_c])
