"""Setting 模型测试用例。"""
import pytest
from django.core.exceptions import ValidationError

from apps.settings.models import Setting


class TestSettingModel:
    """Setting 模型基本 CRUD 和 cleaned_value 属性测试。"""

    def test_create_setting(self, db):
        """创建基本设置项。"""
        s = Setting.objects.create(name='TEST_KEY', value='"test_value"', category='test')
        assert s.name == 'TEST_KEY'
        assert s.cleaned_value == 'test_value'

    def test_cleaned_value_int(self, db):
        """cleaned_value 正确反序列化整数。"""
        s = Setting.objects.create(name='NUM', value='42', category='test')
        assert s.cleaned_value == 42

    def test_cleaned_value_bool(self, db):
        """cleaned_value 正确反序列化布尔值。"""
        s = Setting.objects.create(name='FLAG', value='true', category='test')
        assert s.cleaned_value is True

    def test_cleaned_value_list(self, db):
        """cleaned_value 正确反序列化列表。"""
        s = Setting.objects.create(
            name='LIST', value='["a", "b", "c"]', category='test'
        )
        assert s.cleaned_value == ['a', 'b', 'c']

    def test_cleaned_value_empty(self, db):
        """空字符串返回 None。"""
        s = Setting.objects.create(name='EMPTY', value='', category='test')
        assert s.cleaned_value is None

    def test_cleaned_value_setter_list(self, db):
        """设置列表值后正确序列化存储。"""
        s = Setting.objects.create(name='SET_LIST', value='', category='test')
        s.cleaned_value = [1, 2, 3]
        s.save()
        s.refresh_from_db()
        assert s.cleaned_value == [1, 2, 3]

    def test_cleaned_value_setter_dict(self, db):
        """设置字典值后正确序列化存储。"""
        s = Setting.objects.create(name='SET_DICT', value='', category='test')
        s.cleaned_value = {'key': 'val'}
        s.save()
        s.refresh_from_db()
        assert s.cleaned_value == {'key': 'val'}

    def test_unique_name_constraint(self, db):
        """同名设置项不可重复创建。"""
        Setting.objects.create(name='DUP', value='"a"')
        with pytest.raises(ValidationError):
            s2 = Setting(name='DUP', value='"b"')
            s2.full_clean()

    def test_update_or_create_new(self, db):
        """创建不存在的设置项。"""
        changed, s = Setting.update_or_create(
            name='NEW_KEY', value='new_value', category='storage'
        )
        assert changed is True
        assert s.cleaned_value == 'new_value'
        assert s.category == 'storage'

    def test_update_or_create_existing_same(self, db):
        """更新已存在但值相同的设置项——不应标记为变更。"""
        Setting.objects.create(name='SAME', value='"hello"', category='test')
        changed, s = Setting.update_or_create(
            name='SAME', value='hello', category='test'
        )
        assert changed is False

    def test_update_or_create_existing_diff(self, db):
        """更新已存在且值不同的设置项——应标记为变更。"""
        Setting.objects.create(name='DIFF', value='"old"', category='test')
        changed, s = Setting.update_or_create(
            name='DIFF', value='new', category='test'
        )
        assert changed is True
        assert s.cleaned_value == 'new'

    def test_refresh_setting(self, db, settings):
        """refresh_setting 将 cleaned_value 写入 Django settings。"""
        s = Setting.objects.create(name='REFRESH_TEST', value='"refreshed"')
        s.refresh_setting()
        assert getattr(settings, 'REFRESH_TEST') == 'refreshed'

    def test_is_active_default(self, db):
        """默认 is_active=True。"""
        s = Setting.objects.create(name='ACTIVE', value='"yes"')
        assert s.is_active is True
