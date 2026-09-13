"""Sonda: ¿dónde se pierde ``record[name] = value`` en una fila LLANA?

Traza, durante ``compute_value`` sobre ``OwnerA4Plain``, cada eslabón de la
escritura —``_model_setitem`` → ``FieldDescriptor.__set__`` → ``_field_write``
→ ``_update_cache``— y publica al final las claves de la caché del campo y
``_cache_missing_ids``. Veredicto por contenido: la caché debe contener el pk.
"""
import os, sys, traceback
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))
import django
django.setup()
from django.db import connection, models
import orm.fields as F
from orm.models import BaseModel
from orm.fields import get_environment
from orm.model_classes import ensure_field_setup

class PartnerPr(models.Model):
    name = models.CharField(max_length=32)
    class Meta:
        app_label = 'base'; db_table = 'probe_partner_pr'

class OwnerPr(models.Model):
    partner = models.ForeignKey(PartnerPr, on_delete=models.CASCADE, null=True)
    partner_name = models.CharField(max_length=32, related='partner.name')
    class Meta:
        app_label = 'base'; db_table = 'probe_owner_pr'

ensure_field_setup()
field = OwnerPr._meta.get_field('partner_name')
print('compute=', field.compute, '| related=', field.related, '| store=', field.store,
      '| descriptor=', type(vars(OwnerPr).get(field.attname)).__name__)

def trace(mod, name):
    orig = getattr(mod, name)
    def wrapped(*a, **k):
        print(f'  -> {name}({[type(x).__name__ for x in a[1:]]}, ids={[getattr(x, "pk", x) for x in a[1:2]]})')
        try:
            r = orig(*a, **k); print(f'  <- {name} = {r!r}'); return r
        except Exception as e:
            print(f'  !! {name} raised {type(e).__name__}: {e}'); raise
    setattr(mod, name, wrapped)

trace(F, '_field_write'); trace(F, '_update_cache'); trace(F, '_filter_not_equal_ids')
models.Field.write = F._field_write; models.Field._update_cache = F._update_cache
models.Field._filter_not_equal_ids = F._filter_not_equal_ids
from orm import models as M
orig_set = M._model_setitem
def set_tr(self, key, value):
    print(f'  -> _model_setitem({type(self).__name__} pk={self.pk}, {key!r}, {value!r})')
    return orig_set(self, key, value)
models.Model.__setitem__ = set_tr

with connection.cursor() as cur:   # tablas huerfanas de una corrida rota
    cur.execute('DROP TABLE IF EXISTS probe_owner_pr, probe_partner_pr CASCADE')
with connection.schema_editor() as ed:
    for m in (PartnerPr, OwnerPr):
        ed.create_model(m)
try:
    p = PartnerPr.objects.create(name='Ada'); o = OwnerPr.objects.create(partner=p)
    row = OwnerPr.objects.get(pk=o.pk)
    env = get_environment()
    print('cache antes:', dict(field._get_cache(env)))
    try:
        field.compute_value(row)
    except Exception:
        traceback.print_exc(limit=12)
    cache = dict(field._get_cache(env))
    print('cache despues:', cache, '| missing:', list(field._cache_missing_ids(row)))
    ok = cache.get(row.pk) == 'Ada'
    print('VEREDICTO:', 'OK' if ok else f'FALLA esperado cache[{row.pk}]=Ada leido={cache.get(row.pk)!r}')
finally:
    connection.close()   # la conexion puede quedar INTRANS tras un fallo
    with connection.schema_editor() as ed:
        for m in (OwnerPr, PartnerPr):
            ed.delete_model(m)
sys.exit(0 if ok else 1)
