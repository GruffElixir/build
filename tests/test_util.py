# SPDX-License-Identifier: MIT

from __future__ import annotations

import importlib.util
import pathlib
import re
import unittest.mock

import pytest
import pytest_mock

import build.util


@pytest.mark.parametrize('isolated', [False, pytest.param(True, marks=[pytest.mark.network, pytest.mark.isolated])])
def test_wheel_metadata(package_test_setuptools: str, isolated: bool) -> None:
    metadata = build.util.wheel_metadata(package_test_setuptools, isolated)

    # Setuptools < v69.0.3 (https://github.com/pypa/setuptools/pull/4159) normalized this to dashes
    assert metadata.get('name', '').replace('-', '_') == 'test_setuptools'
    assert metadata.get('version') == '1.0.0'
    assert isinstance(metadata, dict)


@pytest.mark.network
def test_wheel_metadata_isolation(package_test_flit: str) -> None:
    if importlib.util.find_spec('flit_core'):
        pytest.xfail('flit_core is available -- we want it missing!')  # pragma: no cover

    metadata = build.util.wheel_metadata(package_test_flit)

    assert metadata.get('name') == 'test_flit'
    assert metadata.get('version') == '1.0.0'
    assert isinstance(metadata, dict)

    with pytest.raises(
        build.BuildBackendException,
        match=re.escape("Backend 'flit_core.buildapi' is not available."),
    ):
        build.util.wheel_metadata(package_test_flit, isolated=False)


@pytest.mark.network
def test_with_get_requires(package_test_metadata: str) -> None:
    metadata = build.util.wheel_metadata(package_test_metadata)

    # Setuptools < v69.0.3 (https://github.com/pypa/setuptools/pull/4159) normalized this to dashes
    assert metadata.get('name', '').replace('-', '_') == 'test_metadata'
    assert metadata.get('version') == '1.0.0'
    assert metadata.get('summary') == 'hello!'
    assert isinstance(metadata, dict)


def test_project_wheel_metadata_installs_build_requires_fresh(mocker: pytest_mock.MockerFixture) -> None:
    env = mocker.MagicMock()
    env_cm = mocker.MagicMock()
    env_cm.__enter__.return_value = env
    env_cm.__exit__.return_value = False
    mocker.patch('build.util.DefaultIsolatedEnv', return_value=env_cm)

    builder = mocker.MagicMock()
    builder.build_system_requires = {'dep1'}
    builder.get_requires_for_build.return_value = {'dep2'}
    mocker.patch('build.util.ProjectBuilder.from_isolated_env', return_value=builder)
    metadata = unittest.mock.sentinel.metadata
    mocker.patch('build.util._project_wheel_metadata', return_value=metadata)

    assert build.util.project_wheel_metadata('/tmp/project') is metadata

    assert env.install.call_args_list == [
        mocker.call({'dep1'}, _fresh=True),
        mocker.call({'dep2'}),
    ]


def test_project_wheel_metadata_non_isolated(mocker: pytest_mock.MockerFixture) -> None:
    builder = mocker.MagicMock()
    metadata = unittest.mock.sentinel.metadata
    mocker.patch('build.util.ProjectBuilder', return_value=builder)
    mocker.patch('build.util._project_wheel_metadata', return_value=metadata)

    assert build.util.project_wheel_metadata('/tmp/project', isolated=False) is metadata


def test_wheel_metadata_reads_parsed_metadata(tmp_path: pathlib.Path, mocker: pytest_mock.MockerFixture) -> None:
    builder = mocker.MagicMock()
    metadata_dir = tmp_path / 'demo-1.0.dist-info'
    metadata_dir.mkdir()
    (metadata_dir / 'METADATA').write_bytes(b'Metadata-Version: 2.1\nName: demo\nVersion: 1.0\n')
    mocker.patch('build.util.ProjectBuilder', return_value=builder)
    builder.metadata_path.return_value = str(metadata_dir)

    metadata = build.util.wheel_metadata(tmp_path / 'project', isolated=False)

    assert metadata.get('name') == 'demo'
    assert metadata.get('version') == '1.0'

    legacy_metadata = build.util._project_wheel_metadata(builder)
    assert legacy_metadata['Name'] == 'demo'
    assert legacy_metadata['Version'] == '1.0'
