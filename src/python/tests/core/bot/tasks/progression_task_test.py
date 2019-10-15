# Copyright 2019 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Tests for regression_task."""

import json
import os
import unittest

from base import errors
from bot.tasks import progression_task
from datastore import data_types
from tests.test_libs import helpers
from tests.test_libs import test_utils


class WriteToBigqueryTest(unittest.TestCase):
  """Test _write_to_big_query."""

  def setUp(self):
    helpers.patch(self, [
        'google_cloud_utils.big_query.write_range',
    ])

    self.testcase = data_types.Testcase(
        crash_type='type',
        crash_state='state',
        security_flag=True,
        fuzzer_name='libfuzzer',
        overridden_fuzzer_name='libfuzzer_pdf',
        job_type='some_job')

  def test_write(self):
    """Tests write."""
    progression_task._write_to_bigquery(self.testcase, 456, 789)  # pylint: disable=protected-access
    self.mock.write_range.assert_called_once_with(
        table_id='fixeds',
        testcase=self.testcase,
        range_name='fixed',
        start=456,
        end=789)


class TestcaseReproducesInRevisionTest(unittest.TestCase):
  """Test _testcase_reproduces_in_revision."""

  def setUp(self):
    helpers.patch(self, [
        'build_management.build_manager.setup_regular_build',
        'bot.testcase_manager.test_for_crash_with_retries',
        'bot.testcase_manager.check_for_bad_build',
    ])

  def test_error_on_failed_setup(self):
    """Ensure that we throw an exception if we fail to set up a build."""
    os.environ['APP_NAME'] = 'app_name'
    # No need to implement a fake setup_regular_build. Since it's doing nothing,
    # we won't have the build directory properly set.
    with self.assertRaises(errors.BuildSetupError):
      progression_task._testcase_reproduces_in_revision(  # pylint: disable=protected-access
          None, '/tmp/blah', 'job_type', 1)


@test_utils.with_cloud_emulators('datastore')
class UpdateIssueMetadataTest(unittest.TestCase):
  """Test _update_issue_metadata."""

  def setUp(self):
    helpers.patch(self, [
        'bot.fuzzers.engine_common.find_fuzzer_path',
        'bot.fuzzers.engine_common.get_all_issue_metadata',
    ])

    data_types.FuzzTarget(engine='libFuzzer', binary='fuzzer').put()
    self.mock.get_all_issue_metadata.return_value = {
        'issue_labels': 'label1',
        'issue_components': 'component1',
    }

    self.testcase = data_types.Testcase(
        overridden_fuzzer_name='libFuzzer_fuzzer')
    self.testcase.put()

  def test_update_issue_metadata_non_existent(self):
    """Test update issue metadata a testcase with no metadata."""
    progression_task._update_issue_metadata(self.testcase)  # pylint: disable=protected-access

    testcase = self.testcase.key.get()
    self.assertDictEqual({
        'issue_labels': 'label1',
        'issue_components': 'component1',
    }, json.loads(testcase.additional_metadata))

  def test_update_issue_metadata_replace(self):
    """Test update issue metadata a testcase with different metadata."""
    self.testcase.additional_metadata = json.dumps({
        'issue_labels': 'label1',
        'issue_components': 'component2',
    })
    progression_task._update_issue_metadata(self.testcase)  # pylint: disable=protected-access

    testcase = self.testcase.key.get()
    self.assertDictEqual({
        'issue_labels': 'label1',
        'issue_components': 'component1',
    }, json.loads(testcase.additional_metadata))

  def test_update_issue_metadata_same(self):
    """Test update issue metadata a testcase with the same metadata."""
    self.testcase.additional_metadata = json.dumps({
        'issue_labels': 'label1',
        'issue_components': 'component1',
    })
    self.testcase.put()

    self.testcase.crash_type = 'test'  # Should not be written.
    progression_task._update_issue_metadata(self.testcase)  # pylint: disable=protected-access

    testcase = self.testcase.key.get()
    self.assertDictEqual({
        'issue_labels': 'label1',
        'issue_components': 'component1',
    }, json.loads(testcase.additional_metadata))
    self.assertIsNone(testcase.crash_type)
