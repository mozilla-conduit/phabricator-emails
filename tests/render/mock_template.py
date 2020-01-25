# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from typing import Optional, Dict

from attr import dataclass


class MockTemplateStore:
    last_template_path: Optional[str]
    last_template_params: Optional[Dict]

    def get(self, template_path):
        self.last_template_path = template_path
        return MockTemplate(self)


@dataclass
class MockTemplate:
    store: MockTemplateStore

    def render(self, params):
        self.store.last_template_params = params
        return "html", "text"
