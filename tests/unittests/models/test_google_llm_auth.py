# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
from unittest import mock

from google.adk.models.google_llm import Gemini
from google.genai import types


def test_client_init_with_api_key():
  """Test that Client is initialized with api_key when GOOGLE_API_KEY is set."""
  with mock.patch.dict(
      os.environ, {"GOOGLE_API_KEY": "test-api-key"}, clear=True
  ):
    with mock.patch("google.genai.Client") as mock_client_cls:
      llm = Gemini(model="gemini-1.5-flash")
      _ = llm.api_client

      # Verify Client was initialized with api_key
      mock_client_cls.assert_called_once()
      call_kwargs = mock_client_cls.call_args.kwargs
      assert call_kwargs.get("api_key") == "test-api-key"
      assert "project" not in call_kwargs
      assert "location" not in call_kwargs


def test_client_init_with_project_location():
  """Test that Client is initialized with project/location when GOOGLE_API_KEY is not set."""
  env_vars = {
      "GOOGLE_CLOUD_PROJECT": "test-project",
      "GOOGLE_CLOUD_LOCATION": "us-central1",
  }
  with mock.patch.dict(os.environ, env_vars, clear=True):
    with mock.patch("google.genai.Client") as mock_client_cls:
      llm = Gemini(model="gemini-1.5-flash")
      _ = llm.api_client

      # Verify Client was initialized with project and location
      mock_client_cls.assert_called_once()
      call_kwargs = mock_client_cls.call_args.kwargs
      assert call_kwargs.get("project") == "test-project"
      assert call_kwargs.get("location") == "us-central1"
      assert "api_key" not in call_kwargs
