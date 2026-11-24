"""Registro das fontes. Para incluir uma nova, importe o módulo e coloque na lista."""

from . import adzuna, ashby, greenhouse, gupy, lever, noticias, smartrecruiters, workday

REGISTRY = {m.NAME: m for m in (
    gupy, adzuna, smartrecruiters, workday, greenhouse, lever, ashby, noticias,
)}
