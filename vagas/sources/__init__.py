"""Registro das fontes. Para incluir uma nova, importe o módulo e coloque na lista."""

from . import adzuna, ashby, freelas99, greenhouse, gupy, lever, noticias, smartrecruiters, workana, workday

REGISTRY = {m.NAME: m for m in (
    gupy, adzuna, smartrecruiters, workday, greenhouse, lever, ashby, noticias, workana, freelas99,
)}
