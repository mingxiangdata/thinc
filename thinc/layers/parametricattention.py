from typing import Tuple, Callable, Optional

from ..model import Model
from ..types import Ragged
from ..util import get_width


def ParametricAttention(nO: Optional[int] = None) -> Model:
    """Weight inputs by similarity to a learned vector"""
    return Model("para-attn", forward, init=init, params={"Q": None}, dims={"nO": nO})


def forward(model, Xr: Ragged, is_train: bool) -> Tuple[Ragged, Callable]:
    Q = model.get_param("Q")
    attention, bp_attention = _get_attention(model.ops, Q, Xr.data, Xr.lengths)
    output, bp_output = _apply_attention(model.ops, attention, Xr.data, Xr.lengths)

    def backprop(dYr: Ragged) -> Ragged:
        dX, d_attention = bp_output(dYr.data)
        dQ, dX2 = bp_attention(d_attention)
        model.inc_grad("dQ", dQ)
        dX += dX2
        return Ragged(dX, dYr.lengths)

    return Ragged(output, Xr.lengths), backprop


def init(model: Model, X: Optional[Ragged] = None, Y: Optional[Ragged] = None) -> None:
    if Y is not None:
        model.set_dim("nO", get_width(Y.data))
    model.set_param("Q", model.ops.allocate((model.get_dim("nO"),)))


def _get_attention(ops, Q, X, lengths):
    attention = ops.gemm(X, Q.reshape((-1, 1)))
    attention = ops.softmax_sequences(attention, lengths)

    def get_attention_bwd(d_attention):
        d_attention = ops.backprop_softmax_sequences(d_attention, attention, lengths)
        dQ = ops.gemm(X, d_attention, trans1=True)
        dX = ops.xp.outer(d_attention, Q)
        return dQ, dX

    return attention, get_attention_bwd


def _apply_attention(self, attention, X, lengths):
    output = X * attention

    def apply_attention_bwd(d_output):
        d_attention = (X * d_output).sum(axis=1, keepdims=True)
        dX = d_output * attention
        return dX, d_attention

    return output, apply_attention_bwd