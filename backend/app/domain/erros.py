class RegraDeNegocioError(Exception):
    """Violação de uma regra de negócio — vira HTTP 422 na borda da API."""


class RecursoNaoEncontradoError(Exception):
    """Entidade referenciada não existe — vira HTTP 404 na borda da API."""


class ConflitoError(Exception):
    """Estado do banco impede a operação — vira HTTP 409 na borda da API."""
