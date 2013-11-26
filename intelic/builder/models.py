from django.db import models
from django.utils.translation import ugettext as _
from django.template.defaultfilters import slugify
from django.core.urlresolvers import reverse
from django.conf import settings
from django.utils import timezone
from django.contrib.sites.models import Site

from intelic.jenkins_handler import icjenkinsjob
import os, zipfile, signals

# Create your models here.

# ##################################################
# Abstract models
# ##################################################

class BaseModel(models.Model):
    name            = models.CharField(verbose_name=_('Name'), max_length=128)
    slug            = models.SlugField()

    class Meta:
        abstract = True

    def __unicode__(self):
        return self.name

    def save(self, *args, **kwargs):
        """Override save to make slug"""
        if not self.slug:
            self.slug = slugify(self.name)
        return super(BaseModel, self).save(*args, **kwargs)

# ##################################################
# Product models
# ##################################################

class FormClass(BaseModel):
    pass

class Product(BaseModel):
    desc            = models.CharField(
        verbose_name=_('Description'), max_length=255, blank=True, null=True
    )
    form_class      = models.ForeignKey(FormClass, verbose_name=_('Form class'))
    is_active       = models.BooleanField(
        verbose_name=_('Is active'), default=True
    )

    class Meta:
        verbose_name = _('Product')
        verbose_name_plural = _('Products')

class Baseline(BaseModel):
    product        = models.ManyToManyField(Product)
    desc            = models.CharField(
        verbose_name=_('Description'), max_length=255, blank=True, null=True
    )
    is_active       = models.BooleanField(
        verbose_name=_('Is active'), default=True
    )

    class Meta:
        verbose_name = _('Baseline')
        verbose_name_plural = _('Baselines')

# ##################################################
# Component models
# ##################################################

class ComponentType(BaseModel):
    pass

    class Meta:
        verbose_name = _('Component type')
        verbose_name_plural = _('Component types')

class DefaultComponentValue(models.Model):
    product         = models.ForeignKey(Product, verbose_name=_('Product'))
    component_type  = models.ForeignKey(ComponentType, verbose_name=_('Component Type'))
    default_value   = models.CharField(verbose_name=_('Default value'), max_length=128)

    class Meta:
        verbose_name = _('Default component value')
        verbose_name_plural = _('Default compont values')

    def __unicode__(self):
        return self.default_value

class Component(BaseModel):
    desc            = models.CharField(
        verbose_name=_('Description'), max_length=255, blank=True, null=True
    )
    type            = models.ForeignKey(ComponentType)
    gerrit_url      = models.URLField(
        verbose_name=_('Gerrit URL'), max_length=8192, blank=True, null=True
    )
    patch_file      = models.FileField(
        verbose_name=_('Patch file'), upload_to='uploads/patches/', 
        blank=True, null=True
    )
    product         = models.ManyToManyField(
        Product, verbose_name=_('Product')
    )
    baseline        = models.ManyToManyField(
        Baseline, verbose_name=_('Baseline')
    )
    is_active       = models.BooleanField(
        verbose_name=_('Is active'), default=True
    )

    class Meta:
        verbose_name = _('Component')
        verbose_name_plural = _('Components')

    def upload_source_to_git_repo(self):
        # TODO: Complete the function.
        pass

    def get_gerrit_change_number(self):
        if not self.gerrit_url:
            return None
        return self.gerrit_url.split('/')[-2]

    def save(self, *args, **kwargs):
        """Override save to make slug"""
        if not self.slug:
            self.slug = slugify('%s-%s' % (self.type, self.name))
        return super(Component, self).save(*args, **kwargs)

# ##################################################
# Job models
# ##################################################

class Build(BaseModel):
    product         = models.ForeignKey(Product, verbose_name=_('Product'))
    baseline        = models.ForeignKey(Baseline, verbose_name=_('Baseline'))
    component       = models.ManyToManyField(Component)
    has_components  = models.BooleanField(default=False)
    created_at      = models.DateTimeField(
        verbose_name=_('Create at'), auto_now_add=True
    )

    class Meta:
        verbose_name = _('Build')
        verbose_name_plural = _('Builds')

    def save_components(self, components):
        has_components = False
        for component in components:
            has_components = True
            self.component.add(component)
        if has_components:
            self.has_components = True
            self.save()
        signals.build_added_components.send(sender=self.__class__, instance=self)

    def create_build_job(self):
        self.process_set.create(
            type = 'Build',
            status = 'Processing',
            progress = '0'
        )
        if icjenkinsjob:
            self.create_jenkins_build()

    def create_patches_package(self):
        self.process_set.create(
            type = 'Package',
            status = 'Processing',
            progress = '0'
        )
        signals.pre_patches_package_create.send(sender=self.__class__, instance=self)
        patches_pkg = zipfile.ZipFile(
            self.generate_patches_package_name(), 'w'
        )
        for component in self.component.all():
            patches_pkg.write(
                component.patch_file.path,
                os.path.basename(component.patch_file.name)
            )
        patches_pkg.close()
        signals.post_patches_package_create.send(
            sender=self.__class__, instance=self, patches_package = patches_pkg
        )

    def create_jenkins_build(self):
        gerrit_change_numbers = []
        for component in self.component.all():
            gerrit_id = component.get_gerrit_change_number()
            if gerrit_id:
                gerrit_change_numbers.append(gerrit_id)
        jenkins_params = {
            'changes': ' '.join(gerrit_change_numbers),
            'base_version': self.baseline.name,
            'product': self.product.name,
        }
        # Do Jenkins job.
        icjenkinsjob.trigger_build(jenkins_params)

    def get_absolute_url(self):
        return reverse('build_detail', args=(self.slug, ))

    def get_config_file_content(self):
        config_file_content = ''
        for component in self.component.all():
            config_file_content += '%s=%s\n' % (component.type, component.name)
        return config_file_content

    def generate_patches_package_name(self, root = settings.MEDIA_ROOT):
        return os.path.join(root, 'patches', self.slug + '.zip')

    def save(self, *args, **kwargs):
        """Override save to make name"""
        now = timezone.now()
        self.name = '%s-%s-%s' % (
            self.product, self.baseline, now.strftime("%Y-%m-%d-%H:%M:%S")
        )
        return super(Build, self).save(*args, **kwargs)

    def update_process(self):
        signals.update_process.send(sender=self.__class__, instance=self)

class Process(models.Model):
    build           = models.ForeignKey(Build)
    type            = models.CharField(verbose_name=_('Name'), max_length=128)
    url             = models.URLField(blank=True, null=True)
    status          = models.CharField(max_length=11, blank=True, null=True)
    progress        = models.IntegerField(default=0)
    message         = models.CharField(max_length=8192, blank=True, null=True)
    started_at      = models.DateTimeField(
        verbose_name=_('Started at'), auto_now_add=True
    )

    class Meta:
        verbose_name = _('Process')
        verbose_name_plural = _('Processes')

    def __unicode__(self):
        return self.url

def component_form_post_save_handler(sender, instance, **kwargs):
    instance.create_build_job()
    if instance.has_components:
        instance.create_patches_package()

def update_process_handler(sender, instance, **kwargs):
    # Fake data here
    now = timezone.now()
    processes = instance.process_set.all()
    for process in processes:
        if process.progress == 100:
            continue

        if process.type == 'Build':
            process.progress = float((now - process.started_at).seconds)/10800*100
            if process.progress == 100:
                process.status = 'Completed'
                if instance.has_components:
                    process.message = '<a href="/media/default/baylake-eng-fastboot-eng.chenxf.zip" class="btn">Download</a>'
                else:
                    process.message = '<a href="/media/all_patched/baylake-eng-fastboot-eng.chenxf.zip" class="btn">Download</a>'
            process.save()

        if process.type == 'Package':
            process.progress = float((now - process.started_at).seconds)/30*100
            process.save()

def post_patches_package_create_handler(sender, instance, patches_package, **kwargs):
    url = 'http://%s%s' % (
        Site.objects.get_current(),
        instance.generate_patches_package_name(root = settings.MEDIA_URL)
    )
    instance.process_set.filter(type = 'Package').update(url = url)

signals.build_added_components.connect(component_form_post_save_handler, sender=Build)
signals.update_process.connect(update_process_handler, sender=Build)
signals.post_patches_package_create.connect(post_patches_package_create_handler, sender=Build)
