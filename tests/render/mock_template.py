# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from typing import Optional
from attr import dataclass


class MockTemplateStore:
    _last_template_path: Optional[str]
    _last_template_params: Optional[dict]

    def get(self, template_path: str):
        self._last_template_path = template_path
        return MockTemplate(self)

    def last_template_path(self):
        assert self._last_template_path
        return self._last_template_path

    def last_template_params(self):
        assert self._last_template_params
        return self._last_template_params


@dataclass
class MockTemplate:
    store: MockTemplateStore

    def render(self, params):
        self.store._last_template_params = params
        return "html", "text"
