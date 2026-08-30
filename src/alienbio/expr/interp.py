"""The Expr interpreter — ``evaluate(form, env)`` and the special forms (M47.1).

| Form | Evaluates to |
|---|---|
| literal | itself |
| ``Name`` | ``env.lookup(path)`` — unbound is an error |
| data | the list / mapping of its evaluated elements, one child seed per key |
| ``Quoted`` | a :class:`QuotedForm` — the form closed over ``env``, a ``Dist`` |
| call of a **function** | arguments evaluated (child seed per argument), then called |
| call of an **expander** | the head gets the argument forms + env, returns a form; evaluated |
| call of a **special form** | the head gets the argument forms + env, returns the value |

The special forms are the whole control surface: ``let``, ``each``, ``if``,
``quote``, ``run``, ``template``, ``seed`` (and the short-circuit ``op:and`` /
``op:or`` the inline parser emits). Anything more is a Python expander.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional, Sequence

from ..suite.dist import Seed
from .env import Env, ExprError, Lazy
from .form import Call, Name, Quoted, is_form
from .registry import Head, special

__all__ = ["evaluate", "QuotedForm", "TemplateHead", "ExprError"]


# ---------------------------------------------------------------------------
# values the interpreter produces
# ---------------------------------------------------------------------------


@dataclass(frozen=True, eq=False)
class QuotedForm:
    """A quoted form as a value: the form plus the environment it was written
    in. It *is* a ``suite.dist.Dist`` (``sample(seed)`` evaluates the form
    under that seed) and exposes ``run`` for evaluation with extra bindings."""

    form: Any
    env: Env

    def sample(self, seed: Seed) -> Any:
        return evaluate(self.form, self.env.with_seed(seed))

    def run(self, bindings: Optional[Mapping[str, Any]] = None, *, seed: Optional[Seed] = None) -> Any:
        env = self.env if seed is None else self.env.with_seed(seed)
        if bindings:
            env = env.bind(**dict(bindings))
        return evaluate(self.form, env)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, QuotedForm) and other.form == self.form

    def __hash__(self) -> int:
        return hash(repr(self.form))

    def __repr__(self) -> str:
        return f"QuotedForm({self.form!r})"


class TemplateHead(Head):
    """A head made by the ``template`` special form: positional parameter
    names, keyword parameters with default forms, a body, and the defining
    environment (closure). Calling it evaluates the body in a child scope of
    the definition scope, under the *call's* seed and namespace."""

    def __init__(
        self,
        name: str,
        positional: Sequence[str],
        params: Mapping[str, Any],
        body: Any,
        env: Env,
    ) -> None:
        super().__init__(name=name, kind="template", fn=self.expand, meta={"summary": f"template {name}"})
        self.positional = tuple(positional)
        self.params = dict(params)
        self.body = body
        self.env_def = env

    def expand(self, args: Sequence[Any], kwargs: Mapping[str, Any], env: Env) -> Any:
        if len(args) > len(self.positional):
            raise env.error(
                f"template {self.name!r} takes {len(self.positional)} positional argument(s), got {len(args)}"
            )
        bound: dict[str, Any] = {}
        for i, pname in enumerate(self.positional):
            if i < len(args):
                bound[pname] = evaluate(args[i], env.child(pname))
            elif pname in kwargs:
                bound[pname] = evaluate(kwargs[pname], env.child(pname))
            else:
                raise env.error(f"template {self.name!r}: missing positional argument {pname!r}")
        for key, form in kwargs.items():
            if key in self.positional:
                continue
            if key not in self.params:
                raise env.error(f"template {self.name!r} has no parameter {key!r}")
            bound[key] = evaluate(form, env.child(key))
        # Defaults evaluate per call, in the call's seed, in the definition scope
        # extended by what is bound so far (a default may use an earlier parameter).
        scope_env = Env(self.env_def.bindings.child(bound), env.registry, env.ctx, env.path or env.ns, env.depth)
        for key, default in self.params.items():
            if key not in bound:
                bound[key] = evaluate(default, scope_env.child(key))
                scope_env.bindings[key] = bound[key]
        return evaluate(self.body, scope_env)


# ---------------------------------------------------------------------------
# evaluate
# ---------------------------------------------------------------------------


def evaluate(form: Any, env: Env) -> Any:
    """Evaluate ``form`` in ``env``."""
    if env.depth > env.ctx.limits.depth:
        raise env.error(f"evaluation deeper than limits.depth={env.ctx.limits.depth}")
    if isinstance(form, Name):
        return env.lookup(form.path)
    if isinstance(form, Quoted):
        return QuotedForm(form.form, env)
    if isinstance(form, Call):
        return _call(form, env)
    if isinstance(form, Lazy):
        return env._force("<lazy>", form)
    if isinstance(form, dict):
        return {k: evaluate(v, env.child(str(k))) for k, v in form.items()}
    if isinstance(form, (list, tuple)):
        return [evaluate(v, env.child(str(i))) for i, v in enumerate(form)]
    return form


def _call(form: Call, env: Env) -> Any:
    head = env.head(form.head)
    if head.is_special:
        return head.fn(form.args, form.kwargs, env)
    if isinstance(head, TemplateHead):
        return head.expand(form.args, form.kwargs, env.with_ns(env.path))
    if head.is_expander:
        produced = head.fn(form.args, form.kwargs, env.with_ns(env.path))
        return evaluate(produced, env)
    # a function: evaluate the arguments, then call
    args = [evaluate(a, env.child(str(i))) for i, a in enumerate(form.args)]
    kwargs = {k: evaluate(v, env.child(k)) for k, v in form.kwargs.items()}
    if "ctx" in head.injects:
        kwargs["ctx"] = env.ctx
    if "env" in head.injects:
        kwargs["env"] = env
    try:
        return head.fn(*args, **kwargs)
    except ExprError:
        raise
    except TypeError as exc:
        raise env.error(f"{form.head}: {exc}") from exc


# ---------------------------------------------------------------------------
# argument helpers for special forms
# ---------------------------------------------------------------------------


def _arg(args: Sequence[Any], kwargs: Mapping[str, Any], i: int, name: str, env: Env, *, required: bool = True) -> Any:
    """The ``i``-th positional or the ``name`` keyword argument form."""
    if i < len(args):
        return args[i]
    if name in kwargs:
        return kwargs[name]
    if required:
        raise env.error(f"{env.path or '<form>'}: missing argument {name!r}")
    return _MISSING


_MISSING = object()


def _check_kwargs(kwargs: Mapping[str, Any], allowed: Sequence[str], env: Env, head: str) -> None:
    for k in kwargs:
        if k not in allowed:
            raise env.error(f"{head}: unknown keyword {k!r} (expected one of {list(allowed)})")


# ---------------------------------------------------------------------------
# the special forms
# ---------------------------------------------------------------------------


def _let(args: Sequence[Any], kwargs: Mapping[str, Any], env: Env) -> Any:
    _check_kwargs(kwargs, ("bindings", "body"), env, "let")
    bindings = _arg(args, kwargs, 0, "bindings", env)
    body = _arg(args, kwargs, 1, "body", env)
    if not isinstance(bindings, Mapping):
        raise env.error("let: bindings must be a mapping of name -> form")
    scope = env.scope({})
    for key, form in bindings.items():
        scope.bindings[str(key)] = evaluate(form, scope.child(str(key)))
    return evaluate(body, scope.child("body"))


def _each(args: Sequence[Any], kwargs: Mapping[str, Any], env: Env) -> Any:
    _check_kwargs(kwargs, ("over", "as", "body", "key", "where"), env, "each")
    over_form = _arg(args, kwargs, 0, "over", env)
    var = _arg(args, kwargs, 1, "as", env)
    body = _arg(args, kwargs, 2, "body", env)
    key_form = _arg(args, kwargs, 3, "key", env, required=False)
    where = _arg(args, kwargs, 4, "where", env, required=False)
    if isinstance(var, Name):
        var = var.path
    if not isinstance(var, str) or not var.isidentifier():
        raise env.error(f"each: 'as' must be an identifier, got {var!r}")
    over = evaluate(over_form, env.child("over"))
    if isinstance(over, Mapping):
        over = list(over.items())
    try:
        items = list(over)
    except TypeError:
        raise env.error(f"each: 'over' is not iterable ({type(over).__name__})") from None
    if len(items) > env.ctx.limits.entities:
        raise env.error(f"each: {len(items)} elements exceeds limits.entities={env.ctx.limits.entities}")
    result_list: list[Any] = []
    result_map: dict[Any, Any] = {}
    for i, item in enumerate(items):
        scope = env.bind(**{var: item})
        if where is not _MISSING and not evaluate(where, scope.child(f"{i}.where")):
            continue
        if key_form is not _MISSING:
            key = evaluate(key_form, scope.child(f"{i}.key"))
            if key in result_map:
                raise env.error(f"each: duplicate key {key!r}")
            result_map[key] = evaluate(body, scope.child(str(key)))
        else:
            result_list.append(evaluate(body, scope.child(str(i))))
    return result_map if key_form is not _MISSING else result_list


def _if(args: Sequence[Any], kwargs: Mapping[str, Any], env: Env) -> Any:
    _check_kwargs(kwargs, ("cond", "then", "else"), env, "if")
    cond = _arg(args, kwargs, 0, "cond", env)
    then = _arg(args, kwargs, 1, "then", env)
    other = _arg(args, kwargs, 2, "else", env, required=False)
    if evaluate(cond, env.child("cond")):
        return evaluate(then, env.child("then"))
    return None if other is _MISSING else evaluate(other, env.child("else"))


def _quote(args: Sequence[Any], kwargs: Mapping[str, Any], env: Env) -> Any:
    _check_kwargs(kwargs, ("form",), env, "quote")
    return QuotedForm(_arg(args, kwargs, 0, "form", env), env)


def _run(args: Sequence[Any], kwargs: Mapping[str, Any], env: Env) -> Any:
    _check_kwargs(kwargs, ("form", "bindings"), env, "run")
    target = evaluate(_arg(args, kwargs, 0, "form", env), env.child("form"))
    bindings_form = _arg(args, kwargs, 1, "bindings", env, required=False)
    bindings = {} if bindings_form is _MISSING else evaluate(bindings_form, env.child("bindings"))
    if not isinstance(bindings, Mapping):
        raise env.error("run: bindings must be a mapping")
    if isinstance(target, QuotedForm):
        return target.run(bindings, seed=env.ctx.seed)
    if is_form(target) or isinstance(target, (list, dict)):
        return evaluate(target, env.bind(**dict(bindings)) if bindings else env)
    return target


def _seed(args: Sequence[Any], kwargs: Mapping[str, Any], env: Env) -> Any:
    _check_kwargs(kwargs, ("label",), env, "seed")
    label = evaluate(_arg(args, kwargs, 0, "label", env), env.child("label"))
    return env.ctx.seed.child(str(label))


def _template(args: Sequence[Any], kwargs: Mapping[str, Any], env: Env) -> Any:
    _check_kwargs(kwargs, ("positional", "params", "body", "name"), env, "template")
    if args:
        raise env.error("template: use keywords (positional=, params=, body=)")
    positional = kwargs.get("positional", [])
    params = kwargs.get("params", {})
    if "body" not in kwargs:
        raise env.error("template: missing body")
    if not isinstance(positional, (list, tuple)) or not all(isinstance(p, str) and p.isidentifier() for p in positional):
        raise env.error("template: positional must be a list of identifiers")
    if not isinstance(params, Mapping) or not all(isinstance(k, str) and k.isidentifier() for k in params):
        raise env.error("template: params must be a mapping of identifier -> default form")
    dup = set(positional) & set(params)
    if dup:
        raise env.error(f"template: {sorted(dup)} listed both as positional and as params")
    name = kwargs.get("name") or env.path.rsplit(".", 1)[-1] or "template"
    return TemplateHead(str(name), positional, params, kwargs["body"], env)


def _and(args: Sequence[Any], kwargs: Mapping[str, Any], env: Env) -> Any:
    value: Any = True
    for i, a in enumerate(args):
        value = evaluate(a, env.child(str(i)))
        if not value:
            return value
    return value


def _or(args: Sequence[Any], kwargs: Mapping[str, Any], env: Env) -> Any:
    value: Any = False
    for i, a in enumerate(args):
        value = evaluate(a, env.child(str(i)))
        if value:
            return value
    return value


special("let", _let, summary="evaluate body in a child scope holding bindings")
special("each", _each, summary="evaluate body once per element; key= makes a mapping")
special("if", _if, summary="evaluate only the taken branch")
special("quote", _quote, summary="hold a form as a value (a Dist)")
special("run", _run, summary="evaluate a quoted form now, with optional bindings")
special("seed", _seed, summary="an explicit child seed")
special("template", _template, summary="define a callable template (an expander head)")
special("op:and", _and, summary="short-circuit and")
special("op:or", _or, summary="short-circuit or")
