from django.contrib import admin

import models, forms

# ##################################################
# Admins
# ##################################################

class DefaultComponentValueInline(admin.TabularInline):
    model = models.DefaultComponentValue
    extra = 1

class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active')
    list_filter = ('form_class', )
    search_fields = ('name', )
    fields = ('name', 'desc', 'form_class')
    inlines = (DefaultComponentValueInline, )

class PMICAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active')
    search_fields = ('name', )
    fields = ('name', 'desc')

class BaselineAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active')
    search_fields = ('name', )
    filter_horizontal = ('product', )
    fields = ('name', 'product', 'desc')

class ComponentTypeAdmin(admin.ModelAdmin):
    list_display = ('name', )
    search_fields = ('name', )
    fields = ('name', )

class ComponentAdmin(admin.ModelAdmin):
    list_display = ('name', 'type', 'is_active')
    list_filter = ('type', )
    filter_horizontal = ('baseline', 'product')
    fields = ('name', 'desc', 'type', 'baseline', 'product', 'patch_file', 'gerrit_url')

class ProcessInline(admin.TabularInline):
    model = models.Process
    extra = 1

class BuildAdmin(admin.ModelAdmin):
    list_display = ('name', 'baseline', 'product', 'created_at')
    list_filter = ('baseline', 'product')
    search_fields = ('name', )
    inlines = (ProcessInline, )

admin.site.register(models.Product, ProductAdmin)
admin.site.register(models.PMIC, PMICAdmin)
admin.site.register(models.Baseline, BaselineAdmin)
admin.site.register(models.ComponentType, ComponentTypeAdmin)
admin.site.register(models.Component, ComponentAdmin)
admin.site.register(models.Build, BuildAdmin)
