"""The Reason value type: a code plus read-only data, like Change and Issue."""

import copy
import pickle

import pytest

from rowsift.types import Reason, ReasonCode


def test_a_reason_is_a_code_with_data() -> None:
    reason = Reason(ReasonCode.CONTENT_FITS_KIND, {"share": 0.97})
    assert reason.code is ReasonCode.CONTENT_FITS_KIND
    assert reason.data["share"] == 0.97
    assert Reason(ReasonCode.ONLY_CANDIDATE).data == {}


def test_the_code_is_coerced_and_checked() -> None:
    assert Reason("saved_mapping").code is ReasonCode.SAVED_MAPPING  # type: ignore[arg-type]  # plain str is coerced
    with pytest.raises(ValueError, match="not a valid ReasonCode"):
        Reason("nope")  # type: ignore[arg-type]  # proves a bad code is refused


def test_the_data_is_copied_and_read_only() -> None:
    source = {"a": 1}
    reason = Reason(ReasonCode.SAVED_MAPPING, source)
    source["a"] = 2
    assert reason.data == {"a": 1}
    with pytest.raises(TypeError):
        reason.data["b"] = 1  # type: ignore[index]  # proves the data is read-only


def test_the_data_holds_scalars_only() -> None:
    with pytest.raises(TypeError, match="str, int, float or bool"):
        Reason(ReasonCode.SAVED_MAPPING, {"a": [1]})  # type: ignore[dict-item]  # proves a list is refused


def test_a_reason_hashes_compares_and_survives_pickle_and_copy() -> None:
    reason = Reason(ReasonCode.HEADER_MATCHES_ALIAS, {"alias": "celular"})
    twin = Reason(ReasonCode.HEADER_MATCHES_ALIAS, {"alias": "celular"})
    assert reason == twin
    assert hash(reason) == hash(twin)
    assert pickle.loads(pickle.dumps(reason)) == reason
    assert copy.deepcopy(reason) == reason
