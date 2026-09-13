"""El criterio de corpus abierto, ¿consulta la exclusion del criterio cerrado?

La regla excluye a proposito el prefijo de namespace de la referencia (``ir``) y
las palabras que colisionan con el ingles. Si el camino del corpus no consulta
esa exclusion, el gate contradice la regla que aplica: la palabra sale del lexico
cerrado por la puerta de delante y vuelve a entrar por la de atras.

*Metrica:* para cada palabra sonda, su pertenencia al lexico cerrado, a las
particulas, y el veredicto del criterio de corpus, por separado.
*Ciega a:* las palabras que no estan en la lista de sondas — es un control, no
un censo; y a si la exclusion DEBERIA aplicarse al corpus, que es una decision.
"""
import importlib.util
import json
import pathlib
import sys

GATE = pathlib.Path('/home/user/thyrox/src/verify/check_identifier_language.py')

#: Las sondas, con la razon por la que cada una esta aqui.
SUBJECTS = (
    ('ir', 'prefijo de namespace de la referencia — excluido del lexico cerrado'),
    ('vals', 'convencion de dict de la referencia; homografo del ingles'),
    ('es', 'codigo de idioma y particula española de dos letras'),
    ('q', 'una letra: nombre de variable corriente'),
    ('iban', 'estandar bancario; homografo de una forma verbal española'),
    ('clasificar', 'palabra española inequivoca — control positivo'),
)


def load_gate():
    spec = importlib.util.spec_from_file_location('gate', GATE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    gate = load_gate()
    rows = []
    for word, reason in SUBJECTS:
        rows.append({
            'word': word,
            'reason': reason,
            'in_closed_lexicon': word in getattr(gate, 'SPANISH_WORDS', ()),
            'in_particles': word in getattr(gate, 'SPANISH_PARTICLES', ()),
            'by_corpus': bool(gate.spanish_by_corpus(word)),
            'length': len(word),
        })
    escapes = [r['word'] for r in rows
               if r['by_corpus'] and not r['in_closed_lexicon']
               and not r['in_particles'] and r['word'] != 'clasificar']
    json.dump({
        'corpus_available': gate.corpus_available(),
        'subjects': rows,
        'caught_only_by_corpus': escapes,
        'closed_lexicon_size': len(getattr(gate, 'SPANISH_WORDS', ())),
    }, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write('\n')


if __name__ == '__main__':
    main()
