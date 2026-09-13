"""Los modelos de la suite del ORM — ≙ ``odoo19c: odoo/addons/test_orm/models/test_orm.py``.

Adaptado de Odoo Community (LGPL-3): copia + adaptación con atribución, que es
el mecanismo que su manifest autoriza (DEC-KX-03). El porte es casi literal —
lo que cambia es el vocabulario de importación, porque aquí los primitivos del
ORM viven en la raíz ``src/`` espejada y no bajo un paquete ``odoo``.

Estos modelos no son producto: son el **sujeto** contra el que la suite mide el
porte de ``src/orm``. Un símbolo presente con la semántica cambiada pasa
cualquier censo de nombres y falla aquí, que es exactamente para lo que existen.
"""
import itertools

import fields
import models
from addons.base.models.timestamped_mixin import TimeStampedModel
from api import depends, onchange
from exceptions import AccessError


class TestOrmCategory(TimeStampedModel):
    """≙ ``:15``."""

    _name = 'test_orm.category'
    _description = 'Test ORM Category'
    _order = 'name'
    _parent_store = True
    _parent_name = 'parent'

    name = fields.Char(required=True)
    color = fields.Integer('Color Index')
    parent = fields.Many2one('test_orm.category', ondelete='cascade')
    parent_path = fields.Char(index=True)
    depth = fields.Integer(compute='_compute_depth')
    root_categ = fields.Many2one('test_orm.category', compute='_compute_root_categ')
    display_name = fields.Char(
        inverse='_inverse_display_name',
        recursive=True,
    )
    dummy = fields.Char(store=False)
    discussions = fields.Many2many('test_orm.discussion', 'test_orm_discussion_category',
                                   'category', 'discussion')

    _positive_color = models.Constraint(
        'CHECK(color >= 0)',
        "The color code must be positive!",
    )

    @depends('name', 'parent.display_name')     # this definition is recursive
    def _compute_display_name(self):
        for cat in self:
            if cat.parent:
                cat.display_name = cat.parent.display_name + ' / ' + cat.name
            else:
                cat.display_name = cat.name

    @depends('parent')
    def _compute_root_categ(self):
        for cat in self:
            current = cat
            while current.parent:
                current = current.parent
            cat.root_categ = current

    @depends('parent_path')
    def _compute_depth(self):
        for cat in self:
            cat.depth = cat.parent_path.count('/') - 1

    def _inverse_display_name(self):
        for cat in self:
            names = cat.display_name.split('/')
            # determine sequence of categories
            categories = []
            for name in names[:-1]:
                category = self.search([('name', 'ilike', name.strip())])
                categories.append(category[0])
            categories.append(cat)
            # assign parents following sequence
            for parent, child in itertools.pairwise(categories):
                if parent and child:
                    child.parent = parent
            # assign name of last category, and reassign display_name (to normalize it)
            cat.name = names[-1].strip()

    def _fetch_query(self, query, fields):
        # DLE P45: `test_31_prefetch`,
        # with self.assertRaises(AccessError):
        #     cat1.name
        if self.search_count([('id', 'in', self._ids), ('name', '=', 'NOACCESS')]):
            msg = 'Sorry'
            raise AccessError(msg)
        return super()._fetch_query(query, fields)


class TestOrmDiscussion(TimeStampedModel):
    """≙ ``:88``."""

    _name = 'test_orm.discussion'
    _description = 'Test ORM Discussion'

    name = fields.Char(string='Title', required=True, help="Description of discussion.")
    # ``related_name='+'`` porta la AUSENCIA de reverso, no la relaja: la
    # fuente nunca crea un accesor inverso implicito —el inverso de un
    # ``Many2one`` alla solo existe si alguien declara un ``One2many`` con su
    # ``inverse_name``— y medido, ninguno lo hace para estos dos, ni aqui ni en
    # ``odoo19c: odoo/addons/test_orm/models/test_orm.py:93,96``. Django si lo
    # crea, y dos campos al mismo destino chocan en ``testormdiscussion_set``
    # (``fields.E304``). Es la convencion dominante del arbol: 197
    # declaraciones ya la usan, y ``One2many.__get__`` la contempla
    # (``src/orm/fields_relational.py:371-373``).
    moderator = fields.Many2one('res.users', related_name='+')
    categories = fields.Many2many('test_orm.category',
        'test_orm_discussion_category', 'discussion', 'category')
    participants = fields.Many2many('res.users', context={'active_test': False},
                                    related_name='+')
    messages = fields.One2many('test_orm.message', 'discussion', copy=True)
    message_concat = fields.Text(string='Message concatenate')
    important_messages = fields.One2many('test_orm.message', 'discussion',
                                         domain=[('important', '=', True)])
    very_important_messages = fields.One2many(
        'test_orm.message', 'discussion',
        domain=lambda self: self._domain_very_important())
    emails = fields.One2many('test_orm.emailmessage', 'discussion')
    important_emails = fields.One2many('test_orm.emailmessage', 'discussion',
                                       domain=[('important', '=', True)])

    history = fields.Json('History', default={'delete_messages': []})
    attributes_definition = fields.PropertiesDefinition('Message Properties')  # see message@attributes

    def _domain_very_important(self):
        """Ensure computed O2M domains work as expected."""
        return [("important", "=", True)]

    @onchange('name')
    def _onchange_name(self):
        # test onchange modifying one2many field values
        if self.env.context.get('generate_dummy_message') and self.name == '{generate_dummy_message}':
            # update body of existings messages and emails
            for message in self.messages:
                message.body = 'not last dummy message'
            for message in self.important_messages:
                message.body = 'not last dummy message'
            # add new dummy message
            message_vals = self.messages._add_missing_default_values({'body': 'dummy message', 'important': True})
            self.messages |= self.messages.new(message_vals)
            self.important_messages |= self.messages.new(message_vals)

    @onchange('moderator')
    def _onchange_moderator(self):
        self.participants |= self.moderator

    @onchange('messages')
    def _onchange_messages(self):
        self.message_concat = "\n".join(["%s:%s" % (m.name, m.body) for m in self.messages])
