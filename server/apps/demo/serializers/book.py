"""书籍序列化器。"""
#!/usr/bin/env python
# -*- coding:utf-8 -*-
# project : xadmin-server
# filename : serializer
# author : ly_13
# date : 6/12/2024

from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from apps.common.core.serializers import BaseModelSerializer, TabsColumn
from apps.common.fields.utils import input_wrapper
from apps.demo import models


class BookSerializer(BaseModelSerializer):
    """书籍序列化器，定义书籍的字段、表单分组及额外参数。"""

    class Meta:
        """序列化器元数据配置。"""

        model = models.Book
        ## pk 字段用于前端删除，更新等标识，如果有删除更新等，必须得加上 pk 字段
        ## 数据返回的字段，该字段受字段权限控制

        ############### 1.使用简易 tabs 表单 #############
        tabs = [
            TabsColumn('基本信息',
                       ['name', 'isbn', 'category', 'is_active', 'author', 'publisher', 'publication_date', 'price',
                        'created_time', 'updated_time']),
            TabsColumn('管理员', ['admin', 'admin2', 'managers', 'managers2']),
            TabsColumn('文件信息', ['avatar', 'cover', 'book_file', 'file', 'files'])
        ]
        fields = ['pk', 'block']
        ########### 单表单结束 ################

        ############### 2.默认的单表单 ##############
        # fields = [
        #     'pk', 'name', 'isbn', 'category', 'is_active', 'author', 'publisher', 'publication_date', 'price', 'block',
        #     'created_time', 'admin', 'admin2', 'managers', 'managers2', 'avatar', 'cover', 'book_file', 'file', 'files',
        #     'updated_time',
        # ]
        ########### 单表单结束 ################

        ## 仅用于前端table表格字段有顺序的展示，如果没定义，默认使用 fields 定义的变量
        ## 为啥要有这个变量？ 一般情况下，前端table表格宽度不够，不需要显示太多字段，就可以通过这个变量来控制显示的字段
        table_fields = [
            'pk', 'cover', 'category', 'name', 'is_active', 'isbn', 'author', 'publisher', 'publication_date', 'price',
            'book_file', 'file', 'files'
        ]

        # fields_unexport = ['pk']  # 导入导出文件时，忽略该字段

        # read_only_fields = ['pk']  # 表示pk字段只读, 和 extra_kwargs 定义的 pk 含义一样

        ## 构建字段的额外参数
        # # extra_kwargs包含了admin 单对多的两种方式，managers 多对多的两种方式，区别在于自定义的input_type，
        # # 观察前端页面变化和 search-columns 请求的数据
        extra_kwargs = {
            'pk': {'read_only': True, 'label': _('Primary key'), 'help_text': _('Unique identifier of the book')},
            'name': {'label': _('Book name'), 'help_text': _('Name of the book')},
            'isbn': {'label': _('ISBN'), 'help_text': _('International Standard Book Number of the book')},
            'category': {'label': _('Category'), 'help_text': _('Category of the book (novel, literature, philosophy)')},
            'is_active': {'label': _('Active'), 'help_text': _('Whether the book is active')},
            'author': {'label': _('Author'), 'help_text': _('Author of the book')},
            'publisher': {'label': _('Publisher'), 'help_text': _('Publisher of the book')},
            'publication_date': {'label': _('Publication date'), 'help_text': _('Publication date of the book')},
            'price': {'label': _('Price'), 'help_text': _('Sale price of the book')},
            'created_time': {'read_only': True, 'label': _('Created time'), 'help_text': _('Time when the book was created')},
            'updated_time': {'read_only': True, 'label': _('Updated time'), 'help_text': _('Time when the book was last updated')},
            'admin': {
                'attrs': ['pk', 'username'], 'required': True, 'format': "{username}({pk})",
                'input_type': 'api-search-user', 'label': _('Admin'), 'help_text': _('Primary administrator of the book')
            },
            'admin2': {
                'attrs': ['pk', 'username'], 'required': True, 'format': "{username}({pk})",
                'label': _('Admin 2'), 'help_text': _('Secondary administrator of the book')
            },
            'managers': {
                'attrs': ['pk', 'username'], 'required': True, 'format': "{username}({pk})",
                'input_type': 'api-search-user', 'label': _('Managers'), 'help_text': _('Primary managers of the book')
            },
            'managers2': {
                'attrs': ['pk', 'username'], 'required': False, 'format': "{username}({pk})",
                'label': _('Managers 2'), 'help_text': _('Secondary managers of the book')
            },
            'avatar': {'label': _('Avatar'), 'help_text': _('Thumbnail image of the book cover')},
            'cover': {'label': _('Cover'), 'help_text': _('Original image of the book cover')},
            'book_file': {'label': _('Book file'), 'help_text': _('Stored file of the book')},
            # 多文件关联默认的 input_type为 m2m_related_field_file
            'files': {
                'attrs': ['pk', 'filepath', 'filesize', 'filename'], 'required': False, 'format': "{filename}({pk})",
                'ignore_field_permission': True, 'label': _('Files'), 'help_text': _('Multiple attachments of the book')
            },
            # 单文件关联默认的 input_type为 object_related_field_file  ，为了让前端支持图片上传后回显，需要添加 'input_type_suffix': 'image'
            # ignore_field_permission 忽略上传文件的字段控制权限
            'file': {
                'attrs': ['pk', 'filepath', 'filesize', 'filename'], 'required': True, 'format': "{filename}({pk})",
                'ignore_field_permission': True, 'input_type_suffix': 'image', 'label': _('File'),
                'help_text': _('Single attachment of the book')
            }
        }

    # # 该方法定义了管理字段，和 extra_kwargs 定义的 admin 含义一样，该字段会被序列化为
    # # 定义带有关联关系的字段，比如上面的admin，则额外参数中，input_type 和 attrs 至少存在一个，要不然前端可能会解析失败
    # # { "pk": 2, "username": "admin", "label": "admin(2)" }
    # # attrs 变量，表示展示的字段，有 pk,username 字段， 且 pk 字段是必须的， 比如 'attrs': ['pk']
    # # format 变量，表示label字段展示内容，里面的字段一定是属于 attrs 定义的字段，写错的话，可能会报错
    # # queryset 变量， 表示数据查询对象集合，注意：search-columns 方法中，该字段会有个 choices 变量，并且包含所有queryset数据，
    # #      如果数据量特别大的时候，一定要自定义 input_type， 否则会有问题
    # # input_type 变量， 自定义，如果存在，前端解析定义的类型 api-search-user ，并且 search-columns 方法中，choices变量为 []
    # #      如果数据量特别大的时候，推荐这种写法
    # # 目前，可以注释了，在父类里面，已经定义了 serializer_related_field 字段， 建议写到 extra_kwargs 里面，使用系统会自动生成
    # # 或者 按照下面方法自己定义。
    # # 为啥推荐写到 extra_kwargs ？ 写到extra_kwargs里面，系统会自动传一些参数， 可以省略 queryset , label 等参数
    # admin = BasePrimaryKeyRelatedField(attrs=['pk', 'username'], label="管理员", required=True,
    #                                    format="{username}({pk})", queryset=UserInfo.objects,
    #                                    input_type='api-search-user')

    # # 目前，可以注释了，在父类里面，已经定义了 serializer_choice_field 字段， 系统会自动生成
    # category = LabeledChoiceField(choices=CategoryChoices.choices,
    #                               default=CategoryChoices.DIRECTORY)

    # 自定义 input_type ，设置了 read_only=True 意味着只能通过详情查看，在新增和编辑页面不展示该字段
    # input_type 仅是前端组件渲染识别用， 可以自定义input_type ,但是前端组件得对定义的input_type 进行渲染
    # 前端自定义组件库 src/components/RePlusPage/src/components
    # 渲染组件定义 src/components/RePlusPage/src/utils/columns.tsx
    block = input_wrapper(serializers.SerializerMethodField)(read_only=True, input_type='boolean',
                                                             label=_('Block'), help_text=_('Custom block status'))

    def get_block(self, obj: models.Book) -> bool:
        """返回书籍是否启用的状态。

        Args:
            obj: 书籍模型实例。

        Returns:
            书籍的启用状态。
        """
        return obj.is_active
