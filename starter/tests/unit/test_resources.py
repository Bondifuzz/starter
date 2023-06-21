import pytest

from starter.app.resources import (
    CpuResources,
    InvalidResourceError,
    InvalidUnitError,
    RamResources,
)


@pytest.mark.parametrize(
    argnames=[
        "input_value",
        "output_value",
        "src_units",
        "dst_units",
    ],
    argvalues=[
        (1, 1, "K", "K"),
        (0, 0, "K", "K"),
        (7, 7, "K", "K"),
        (700, 700, "K", "K"),
        (1000, 1024, "Ki", "K"),
        (0, 0, "Ki", "K"),
        (1, 1000, "M", "K"),
        (0, 0, "M", "K"),
        (1, 1000000, "G", "K"),
        (0, 0, "G", "K"),
        (1000, 1, "K", "M"),
        (0, 0, "K", "M"),
        (7000, 7, "K", "M"),
        (1, 1, "M", "M"),
        (0, 0, "M", "M"),
        (7, 7, "M", "M"),
        (1000000, 1048576, "Mi", "M"),
        (0, 0, "Mi", "M"),
        (1, 1000, "G", "M"),
        (0, 0, "G", "M"),
        (7, 7000, "G", "M"),
        (1, 1, "G", "G"),
        (0, 0, "G", "G"),
        (70, 70, "G", "G"),
        (1000, 1, "M", "G"),
        (0, 0, "M", "G"),
        (1000000, 1, "K", "G"),
        (0, 0, "K", "G"),
        (1000000000, 1073741824, "Gi", "G"),
        (1000000000, 1048576, "Mi", "G"),
        (0, 0, "Mi", "G"),
    ],
)
def test_convert_memory(input_value, output_value, src_units, dst_units):
    input_value_str = RamResources.to_string(output_value, dst_units, src_units)
    assert input_value_str == f"{input_value}{src_units}"
    assert RamResources.from_string(input_value_str, dst_units) == output_value


@pytest.mark.parametrize(
    argnames=[
        "input_value",
        "output_value",
        "src_units",
        "dst_units",
    ],
    argvalues=[
        (0.1, 100, "G", "M"),
        (2.1, 2100, "G", "M"),
        (0.001, 1000, "G", "K"),
        (1.2, 1200000, "G", "K"),
        (1.65, 1650, "M", "K"),
    ],
)
def test_convert_memory_float(input_value, output_value, src_units, dst_units):
    input_value_str = f"{input_value}{src_units}"
    assert RamResources.from_string(input_value_str, dst_units) == output_value


def test_convert_memory_invalid_value():

    with pytest.raises(InvalidUnitError):
        RamResources.to_string(12, src_units="Mi", dst_units="Ku")

    with pytest.raises(InvalidUnitError):
        RamResources.to_string(12, src_units="Mu", dst_units="Ki")

    with pytest.raises(InvalidUnitError):
        RamResources.from_string("12M", dst_units="Ku")

    with pytest.raises(InvalidResourceError):
        RamResources.from_string("abc")

    with pytest.raises(InvalidResourceError):
        RamResources.from_string(".12M")

    with pytest.raises(InvalidResourceError):
        RamResources.from_string("12.M")

    with pytest.raises(InvalidResourceError):
        RamResources.from_string("12Ku")

    with pytest.raises(InvalidResourceError):
        RamResources.from_string("123i")

    with pytest.raises(InvalidResourceError):
        RamResources.from_string("Mi")


@pytest.mark.parametrize(
    argnames=[
        "input_value",
        "output_value",
        "src_units",
        "dst_units",
    ],
    argvalues=[
        (1, 1, "m", "m"),
        (0, 0, "m", "m"),
        (7, 7, "m", "m"),
        (700, 700, "m", "m"),
        (1, 1, "n", "n"),
        (0, 0, "n", "n"),
        (7, 7, "n", "n"),
        (700, 700, "n", "n"),
        (1, 1000000, "m", "n"),
        (0, 0, "m", "n"),
        (0, 0, "n", "m"),
    ],
)
def test_convert_cpu(input_value, output_value, src_units, dst_units):
    input_value_str = CpuResources.to_string(output_value, dst_units, src_units)
    assert input_value_str == f"{input_value}{src_units}"
    assert CpuResources.from_string(input_value_str, dst_units) == output_value


@pytest.mark.parametrize(
    argnames=[
        "input_value",
        "output_value",
        "src_units",
        "dst_units",
    ],
    argvalues=[
        (0.001, 1000, "m", "n"),
        (2.1, 2100000, "m", "n"),
    ],
)
def test_convert_cpu_float(input_value, output_value, src_units, dst_units):
    input_value_str = f"{input_value}{src_units}"
    x = CpuResources.from_string(input_value_str, dst_units) == output_value
    assert CpuResources.from_string(input_value_str, dst_units) == output_value


def test_convert_cpu_invalid_value():

    with pytest.raises(InvalidUnitError):
        CpuResources.to_string(12, src_units="m", dst_units="i")

    with pytest.raises(InvalidUnitError):
        CpuResources.to_string(12, src_units="i", dst_units="n")

    with pytest.raises(InvalidUnitError):
        CpuResources.from_string("12m", dst_units="i")

    with pytest.raises(InvalidResourceError):
        CpuResources.from_string("abc")

    with pytest.raises(InvalidResourceError):
        CpuResources.from_string(".12m")

    with pytest.raises(InvalidResourceError):
        CpuResources.from_string("12.m")

    with pytest.raises(InvalidResourceError):
        CpuResources.from_string("123i")

    with pytest.raises(InvalidResourceError):
        CpuResources.from_string("m")
