"""``res.partner.bank`` + IBAN — adaptación de Odoo ``base_iban``.

Adaptación de ``odoo19c: addons/base_iban/models/res_partner_bank.py``
(``odoo-tools@622ddc2aa5563d12295b4ab7d3eb438a43eb31de``, LGPL-3) — atribución
y aviso de licencia preservados (DEC-KX-03).

Porte completo: los **13 símbolos** del archivo de la referencia (5 funciones de
módulo + el mapa de países + 7 métodos de la clase). Ninguno queda fuera; el
mapeo de los que cambian de forma está en la tabla de abajo.

Los siete métodos de ``ResPartnerBank`` conservan **el nombre de la fuente**,
guion bajo incluido, y se instalan uno a uno con nombre literal desde
:func:`apply_base_iban_extensions`.

Cómo se extiende ``res.partner.bank``
======================================

La referencia usa ``_inherit`` y ``super()``. Aquí el idioma equivalente es
colgar funciones de módulo sobre la clase desde ``AppConfig.ready()``, con
``orm.method_chain.chain_method`` como el ``super()`` que ese idioma no tiene
(ver ``orm/method_chain.py`` y :ref:`h-api-364`).

``retrieve_acc_type`` y ``_get_supported_account_types`` son ``@classmethod`` en
nuestro ``base`` — encadenarlos exigió arreglar el mecanismo antes
(:ref:`h-api-381`): ``getattr`` sobre un ``@classmethod`` devuelve un método ya
ligado, así que la cadena pasaba la instancia como argumento extra. Este addon
es su primer consumidor real.

Mapeo de forma frente a la referencia
======================================

===========================  ==================================================
Referencia                   Aquí
===========================  ==================================================
``create(vals_list)``        ``create(cls, vals_list)`` — la misma firma
                             desde :ref:`h-api-1108`; la normalización va en
                             un relevo de ``chain_method`` que devuelve
                             ``None`` y deja el alta al ``create`` previo
``write(vals)``              ``write(self, **vals)`` — el idioma ya establecido
                             para portar ``write`` sobre un modelo sin
                             ``write`` previa (``stock_location.py:575``)
``save()``                   NO está en la fuente: es el punto del stack por el
                             que pasan los dos caminos anteriores, así que
                             normaliza también quien no usa ``create``/``write``
``@api.constrains``          ``_check_iban()`` con su nombre, y ``clean()`` —el
``_check_iban``              hook de Django, 34 precedentes— lo invoca
``@api.model`` +             ``@classmethod`` — el terminal de ``base`` ya
``super()``                  estaba declarado así
``_lt(...)`` con args        ``ValidationError(_('… %(x)s'), params=…)``, la
                             forma de Django para un mensaje con datos
===========================  ==================================================

Divergencia declarada
======================

**El widget JS de entrada de IBAN no se porta.** La referencia declara
``depends: ['account', 'web']`` y sirve ``static/src/js`` — el campo con máscara
del cliente web de Odoo. Este producto expone REST + React; el formateo de
entrada es responsabilidad de ``ui``, y el backend conserva lo que importa: la
validación y el formato canónico al guardar.
"""
import re

from addons.base.models.res_bank import ResPartnerBank
from exceptions import UserError, ValidationError
import api
from orm.method_chain import chain_method, extend_list
from tools.translate import _


def normalize_iban(iban):
    """El número sin separadores — ≙ ``odoo19c: base_iban:12``."""
    return re.sub(r'[\W_]', '', iban or '')


def pretty_iban(iban):
    """El número en grupos de cuatro — ≙ ``odoo19c: base_iban:15``.

    Si no valida, se devuelve tal cual: el formato bonito es una cortesía, no
    una imposición (misma decisión que la referencia, que traga la excepción).
    """
    try:
        validate_iban(iban)
        iban = ' '.join([iban[i:i + 4] for i in range(0, len(iban), 4)])
    except ValidationError:
        # silent OK because el formato bonito es opcional: un número que no
        # valida se devuelve tal cual, igual que en la referencia. Quien
        # necesite el veredicto llama a validate_iban() y lo recibe.
        pass
    return iban


def get_bban_from_iban(iban):
    """El BBAN correspondiente a un IBAN — ≙ ``odoo19c: base_iban:24``.

    Ojo: el BBAN **no** es el número de cuenta doméstico. La relación entre los
    tres está en http://www.ecbs.org/iban.htm.
    """
    return normalize_iban(iban)[4:]


def get_iban_part(iban, number_kind):
    """El tramo del IBAN que la plantilla del país marca — ≙ ``base_iban:31``.

    .. code-block:: python

        # plantilla = 'ITkk KBBB BBSS SSSC CCCC CCCC CCC'
        acc_number = 'IT60X0542811101000000123456'
        get_iban_part(acc_number, 'bank') == '05428'
        get_iban_part(acc_number, 'account') == '000000123456'

    Devuelve ``False`` cuando no se puede — valor de fallo de la referencia, que
    se conserva para no cambiar el contrato de quien lo consuma.
    """
    iban_part_map = {
        # Generales
        'bank': 'B',             # código nacional del banco
        'branch': 'S',           # código de sucursal
        'account': 'C',          # número de cuenta

        # Dígitos de control
        'check': 'k',            # dígitos de control del IBAN
        'check_national': 'K',   # dígitos de control nacionales

        # Especiales por país
        'account_type': 'T',     # tipo de cuenta en Bulgaria y Guatemala
        'balance_account': 'A',  # Balance Account Number de Bielorrusia
        'fiscal_code': 'F',      # Kennitala islandés
        'reserved': 'R',         # cero reservado de Turquía
    }
    if not (mask_char := iban_part_map.get(number_kind.lower())):
        return False

    iban = normalize_iban(iban)
    country_code = iban[:2].lower()

    # Se quita el código de país de ambos: puede llevar caracteres de máscara.
    iban_nocc = iban[2:]
    template_nocc = _map_iban_template.get(country_code, '').replace(' ', '')[2:]
    return template_nocc and "".join(
        c for c, t in zip(iban_nocc, template_nocc) if t == mask_char
    )


def validate_iban(iban):
    """Valida un IBAN — ≙ ``odoo19c: base_iban:68``.

    Tres comprobaciones, en el orden de la referencia: el país está en el mapa,
    la longitud coincide con su plantilla y sólo hay alfanuméricos, y el resto
    mod-97 del número rotado en base 36 es 1 (ISO 13616).
    """
    iban = normalize_iban(iban)
    if not iban:
        raise ValidationError(_('No hay código IBAN.'), code='iban_empty')

    country_code = iban[:2].lower()
    if country_code not in _map_iban_template:
        raise ValidationError(
            _('El IBAN es inválido: debe empezar con el código de país.'),
            code='iban_unknown_country',
        )

    iban_template = _map_iban_template[country_code]
    if len(iban) != len(iban_template.replace(' ', '')) or not re.fullmatch(
            '[a-zA-Z0-9]+', iban):
        raise ValidationError(
            _('El IBAN no parece correcto. Debería tener esta forma: '
              '%(template)s, donde B = código nacional del banco, S = código '
              'de sucursal, C = número de cuenta, k = dígito de control.'),
            params={'template': iban_template},
            code='iban_malformed',
        )

    check_chars = iban[4:] + iban[:4]
    # BASE 36: 0..9, A..Z -> 0..35
    digits = int(''.join(str(int(char, 36)) for char in check_chars))
    if digits % 97 != 1:
        raise ValidationError(
            _('Este IBAN no pasa la verificación; revísalo.'),
            code='iban_checksum',
        )


def _get_supported_account_types(cls):
    """Añade ``iban`` al vocabulario — ≙ ``odoo19c: base_iban:91``.

    ACUMULA: la referencia hace ``rslt = super()...; rslt.append(...)``, así que
    se cuelga con ``combine=extend_list`` y el terminal de ``base`` conserva
    ``bank``.
    """
    return [('iban', _('IBAN'))]


def retrieve_acc_type(cls, acc_number):
    """``iban`` cuando el número valida — ≙ ``odoo19c: base_iban:97``.

    RELEVO: devolver ``None`` delega en la implementación previa, que es
    exactamente lo que la referencia escribe como
    ``return super().retrieve_acc_type(acc_number)``.
    """
    try:
        validate_iban(acc_number)
        return 'iban'
    except ValidationError:
        return None


def _prettify_iban_in_vals(vals):
    """Deja ``acc_number`` en su formato canónico dentro de ``vals``.

    ≙ el cuerpo que la referencia REPITE en ``create`` (``odoo19c:
    base_iban:110-119``) y en ``write`` (``:121-128``): si el número valida
    como IBAN se guarda en grupos de cuatro; si no valida se deja tal cual,
    porque una cuenta doméstica es legítima.

    Se escribe una vez y la usan los dos, en vez de repetirla como la fuente:
    allá son dos cuerpos idénticos, y aquí serían tres con ``save``.
    """
    if not vals.get('acc_number'):
        return vals
    try:
        validate_iban(vals['acc_number'])
    except ValidationError:
        # silent OK because guardar un número que no es IBAN es legítimo (una
        # cuenta doméstica); sólo se deja de reformatear. El rechazo de un
        # IBAN inválido lo hace _check_iban(), no este ayudante.
        return vals
    vals['acc_number'] = pretty_iban(normalize_iban(vals['acc_number']))
    return vals


def create(cls, vals_list):
    """Alta con el IBAN ya normalizado — ≙ ``create`` (``odoo19c: base_iban:110``).

    La referencia es ``@api.model_create_multi``: recibe una **lista** de
    dicts, normaliza cada ``acc_number`` y delega en ``super().create``. Aquí
    la firma es la misma desde :ref:`h-api-1108` —``DefaultGetMixin.create``
    porta ``BaseModel.create`` por contenido y ``base.ResPartnerBank`` lo
    adopta— y el ``super()`` de la fuente es el **relevo por ``None``** de
    ``chain_method``: este eslabón normaliza ``vals`` **en sitio** y devuelve
    ``None``, con lo que la cadena entrega la misma lista, ya bonita, al
    ``create`` previo.

    Hasta ese hallazgo el docstring de este método decía *"se porta el paso,
    no la firma"* y su cuerpo era ``cls(**vals).save()`` — un alta sin
    defaults, sin ``check_access`` y sin el resto de pasos de la fuente. La
    normalización es idempotente, igual que allá (su ``super().create``
    recalcula ``acc_type`` sobre el número ya bonito), así que el ``save()``
    encadenado de este addon puede volver a pasar por ella.
    """
    for vals in vals_list:
        _prettify_iban_in_vals(vals)
    return None


def write(self, **vals):
    """Escritura con el IBAN ya normalizado — ≙ ``write`` (``base_iban:121``).

    Mismo cuerpo que ``create`` en la fuente, y misma razón para existir aparte
    de ``save``: la fuente intercepta los valores **antes** de que lleguen a la
    fila, no la fila ya construida.

    La firma es ``**vals`` y el cuerpo es *poner los atributos y guardar*,
    que es el idioma ya establecido en este árbol para portar el ``write`` de
    la referencia sobre un modelo sin ``write`` previa —
    ``addons/stock/models/stock_location.py:575``,
    ``stock_package_type.py:318``, ``stock_quant.py:868``. Devuelve ``self``,
    como esos tres.
    """
    vals = _prettify_iban_in_vals(dict(vals))
    for name, value in vals.items():
        setattr(self, name, value)
    self.save()
    return self


def get_bban(self):
    """El BBAN de esta cuenta — ≙ ``odoo19c: base_iban:105``."""
    if self.acc_type != 'iban':
        raise UserError(
            _('No se puede calcular el BBAN porque el número de cuenta no es '
              'un IBAN.'))
    return get_bban_from_iban(self.acc_number)


def save(self, *args, **kwargs):
    """Guarda el IBAN en su formato canónico — ≙ ``create`` + ``write``.

    La referencia repite el mismo cuerpo en los dos (``base_iban:110`` y
    ``:121``) porque su ORM separa alta y modificación; aquí ambos caminos
    pasan por ``save()``, así que el hook es uno.

    Devuelve ``None`` a propósito: eso hace que ``chain_method`` delegue en el
    ``save()`` de ``base``, que deriva ``sanitized_acc_number`` y ``acc_type``
    y persiste. Es el mismo ``return super().create(...)`` de la referencia.
    """
    if self.acc_number:
        try:
            validate_iban(self.acc_number)
            self.acc_number = pretty_iban(normalize_iban(self.acc_number))
        except ValidationError:
            # silent OK because guardar un número que no es IBAN es legítimo
            # (una cuenta doméstica); sólo se deja de reformatear. El rechazo
            # de un IBAN inválido lo hace clean(), no este hook.
            pass


def _check_iban(self):
    """Un IBAN declarado tiene que validar — ≙ ``_check_iban``, ``base_iban:130``.

    Conserva el **nombre de la fuente, guion bajo incluido**: allá es
    ``@api.constrains('acc_number')``, es decir superficie interna que el ORM
    invoca y nadie llama desde fuera. Quitarle el guion bajo lo promovería a
    API pública, que es un contrato que la fuente nunca ofreció
    (``porte-completo-no-parcial.md``, «el guion bajo se porta»).

    La referencia itera ``for bank in self`` porque su ``self`` es un
    recordset; aquí es una instancia, así que el bucle desaparece y el cuerpo
    es el mismo.

    Lee ``acc_type``, que allí es un ``compute`` siempre fresco y aquí es
    **columna almacenada**: leerla es la comprobación *más fuerte*, porque
    atrapa una fila marcada ``iban`` cuyo ``acc_number`` se editó por un camino
    que no pasó por ``save()``.
    """
    if self.acc_type == 'iban':
        validate_iban(self.acc_number)


def clean(self):
    """El hook de validación de Django — invoca ``_check_iban``.

    ``@api.constrains`` no tiene contraparte directa: el punto que este stack
    ofrece para «valida antes de aceptar la fila» es ``Model.clean()``, con 34
    precedentes en ``src/addons/``. Por eso el constraint de la referencia
    conserva su nombre en :func:`_check_iban` y ``clean`` sólo lo llama — así
    el símbolo portado es el de la fuente, y el hook del stack es el puente.
    """
    self._check_iban()


def check_iban(self, iban=''):
    """¿Valida este número? — ≙ ``odoo19c: base_iban:136``.

    La forma booleana, para quien prefiera preguntar en vez de capturar.
    """
    try:
        validate_iban(iban)
        return True
    except ValidationError:
        return False


def apply_base_iban_extensions():
    """Cuelga la superficie IBAN sobre ``base.ResPartnerBank``.

    La llama ``BaseIbanConfig.ready()``, no el import del módulo: en tiempo de
    import el registro de modelos aún no está poblado.
    """
    # ACUMULA — el terminal de ``base`` aporta ``bank`` y este addon ``iban``.
    chain_method(ResPartnerBank, '_get_supported_account_types',
                 _get_supported_account_types, combine=extend_list)

    # RELEVO — cada eslabón atiende su país y devuelve ``None`` para el resto.
    # Es el punto que ``base/models/res_partner_bank.py:retrieve_acc_type``
    # reservaba, y el que obligó a arreglar ``chain_method`` (:ref:`h-api-381`).
    chain_method(ResPartnerBank, 'retrieve_acc_type', retrieve_acc_type)

    # RELEVO sobre los dos hooks del ciclo de vida.
    chain_method(ResPartnerBank, 'save', save)
    chain_method(ResPartnerBank, 'clean', clean)

    # Métodos nuevos: no había previa, se instalan tal cual. Van uno por uno y
    # NO en un bucle: el bucle pasaba el nombre en una variable, así que el
    # recorrido AST de ``scripts/check_porte_completo.py`` leía ``name`` en vez
    # del símbolo y los daba por no portados. Un nombre literal por llamada es
    # lo que hace la instalación atribuible.
    chain_method(ResPartnerBank, 'get_bban', get_bban)
    chain_method(ResPartnerBank, 'check_iban', check_iban)
    chain_method(ResPartnerBank, '_check_iban', _check_iban)
    chain_method(ResPartnerBank, 'write', write)
    chain_method(ResPartnerBank, 'create', api.model_create_multi(classmethod(create)))

#: Mapa ISO 3166-1 -> plantilla IBAN, copiado verbatim de la referencia
#: (``odoo19c: base_iban:146-218``, 70 países). La descripción del formato
#: por país está en
#: http://en.wikipedia.org/wiki/International_Bank_Account_Number#IBAN_formats_by_country
_map_iban_template = {
    'ad': 'ADkk BBBB SSSS CCCC CCCC CCCC',  # Andorra
    'ae': 'AEkk BBBC CCCC CCCC CCCC CCC',  # United Arab Emirates
    'al': 'ALkk BBBS SSSK CCCC CCCC CCCC CCCC',  # Albania
    'at': 'ATkk BBBB BCCC CCCC CCCC',  # Austria
    'az': 'AZkk BBBB CCCC CCCC CCCC CCCC CCCC',  # Azerbaijan
    'ba': 'BAkk BBBS SSCC CCCC CCKK',  # Bosnia and Herzegovina
    'be': 'BEkk BBBC CCCC CCKK',  # Belgium
    'bg': 'BGkk BBBB SSSS TTCC CCCC CC',  # Bulgaria
    'bh': 'BHkk BBBB CCCC CCCC CCCC CC',  # Bahrain
    'br': 'BRkk BBBB BBBB SSSS SCCC CCCC CCCT N',  # Brazil
    'by': 'BYkk BBBB AAAA CCCC CCCC CCCC CCCC',  # Belarus
    'ch': 'CHkk BBBB BCCC CCCC CCCC C',  # Switzerland
    'cr': 'CRkk BBBC CCCC CCCC CCCC CC',  # Costa Rica
    'cy': 'CYkk BBBS SSSS CCCC CCCC CCCC CCCC',  # Cyprus
    'cz': 'CZkk BBBB SSSS SSCC CCCC CCCC',  # Czech Republic
    'de': 'DEkk BBBB BBBB CCCC CCCC CC',  # Germany
    'dk': 'DKkk BBBB CCCC CCCC CC',  # Denmark
    'do': 'DOkk BBBB CCCC CCCC CCCC CCCC CCCC',  # Dominican Republic
    'ee': 'EEkk BBSS CCCC CCCC CCCK',  # Estonia
    'es': 'ESkk BBBB SSSS KKCC CCCC CCCC',  # Spain
    'fi': 'FIkk BBBB BBCC CCCC CK',  # Finland
    'fo': 'FOkk CCCC CCCC CCCC CC',  # Faroe Islands
    'fr': 'FRkk BBBB BSSS SSCC CCCC CCCC CKK',  # France
    'gb': 'GBkk BBBB SSSS SSCC CCCC CC',  # United Kingdom
    'ge': 'GEkk BBCC CCCC CCCC CCCC CC',  # Georgia
    'gi': 'GIkk BBBB CCCC CCCC CCCC CCC',  # Gibraltar
    'gl': 'GLkk BBBB CCCC CCCC CC',  # Greenland
    'gr': 'GRkk BBBS SSSC CCCC CCCC CCCC CCC',  # Greece
    'gt': 'GTkk BBBB MMTT CCCC CCCC CCCC CCCC',  # Guatemala
    'hr': 'HRkk BBBB BBBC CCCC CCCC C',  # Croatia
    'hu': 'HUkk BBBS SSSC CCCC CCCC CCCC CCCC',  # Hungary
    'ie': 'IEkk BBBB SSSS SSCC CCCC CC',  # Ireland
    'il': 'ILkk BBBS SSCC CCCC CCCC CCC',  # Israel
    'is': 'FSkk BBBB SSCC CCCC FFFF FFFF FF',  # Iceland
    'it': 'ITkk KBBB BBSS SSSC CCCC CCCC CCC',  # Italy
    'jo': 'JOkk BBBB SSSS CCCC CCCC CCCC CCCC CC',  # Jordan
    'kw': 'KWkk BBBB CCCC CCCC CCCC CCCC CCCC CC',  # Kuwait
    'kz': 'KZkk BBBC CCCC CCCC CCCC',  # Kazakhstan
    'lb': 'LBkk BBBB CCCC CCCC CCCC CCCC CCCC',  # Lebanon
    'li': 'LIkk BBBB BCCC CCCC CCCC C',  # Liechtenstein
    'lt': 'LTkk BBBB BCCC CCCC CCCC',  # Lithuania
    'lu': 'LUkk BBBC CCCC CCCC CCCC',  # Luxembourg
    'lv': 'LVkk BBBB CCCC CCCC CCCC C',  # Latvia
    'mc': 'MCkk BBBB BSSS SSCC CCCC CCCC CKK',  # Monaco
    'md': 'MDkk BBCC CCCC CCCC CCCC CCCC',  # Moldova
    'me': 'MEkk BBBC CCCC CCCC CCCC KK',  # Montenegro
    'mk': 'MKkk BBBC CCCC CCCC CKK',  # Macedonia
    'mr': 'MRkk BBBB BSSS SSCC CCCC CCCC CKK',  # Mauritania
    'mt': 'MTkk BBBB SSSS SCCC CCCC CCCC CCCC CCC',  # Malta
    'mu': 'MUkk BBBB BBSS CCCC CCCC CCCC CCCC CC',  # Mauritius
    'nl': 'NLkk BBBB CCCC CCCC CC',  # Netherlands
    'no': 'NOkk BBBB CCCC CCK',  # Norway
    'om': 'OMkk BBBC CCCC CCCC CCCC CCC', # Oman
    'pk': 'PKkk BBBB CCCC CCCC CCCC CCCC',  # Pakistan
    'pl': 'PLkk BBBS SSSK CCCC CCCC CCCC CCCC',  # Poland
    # Palestinian territories: Wikipedia has no 'X's, just uses 'C', Harvard reference does the same.
    'ps': 'PSkk BBBB CCCC CCCC CCCC CCCC CCCC C',  # Palestinian
    'pt': 'PTkk BBBB SSSS CCCC CCCC CCCK K',  # Portugal
    'qa': 'QAkk BBBB CCCC CCCC CCCC CCCC CCCC C',  # Qatar
    'ro': 'ROkk BBBB CCCC CCCC CCCC CCCC',  # Romania
    'rs': 'RSkk BBBC CCCC CCCC CCCC KK',  # Serbia
    'sa': 'SAkk BBCC CCCC CCCC CCCC CCCC',  # Saudi Arabia
    'se': 'SEkk BBBB CCCC CCCC CCCC CCCC',  # Sweden
    'si': 'SIkk BBSS SCCC CCCC CKK',  # Slovenia
    'sk': 'SKkk BBBB SSSS SSCC CCCC CCCC',  # Slovakia
    'sm': 'SMkk KBBB BBSS SSSC CCCC CCCC CCC',  # San Marino
    'tn': 'TNkk BBSS SCCC CCCC CCCC CCCC',  # Tunisia
    'tr': 'TRkk BBBB BRCC CCCC CCCC CCCC CC',  # Turkey
    'ua': 'UAkk BBBB BBCC CCCC CCCC CCCC CCCC C',  # Ukraine
    'vg': 'VGkk BBBB CCCC CCCC CCCC CCCC',  # Virgin Islands
    'xk': 'XKkk BBBB CCCC CCCC CCCC',  # Kosovo
}
