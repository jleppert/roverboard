from django.shortcuts import render

# Create your views here.


import mimetypes
from django.views.generic.base import TemplateView
from django.views.generic.edit import FormView
from django import forms
from django.conf import settings
import datetime
import glob
import os
import requests
from django.http import HttpResponse

class ScanDetailView(TemplateView):
    pass

def download_file(request,filename):
    # fill these variables with real values


    if '/' in filename or '..' in filename:
        #don't allow these characters to move directories
        return

    path = os.path.join(settings.SCAN_DATA_DIR, filename+'o')
    fl = open(path, 'rb')
    response = HttpResponse(fl, content_type='application/force-download')
    download_name = '{}.DZT'.format(filename)
    response['Content-Disposition'] = "attachment; filename=%s" % download_name
    return response

class RoverForm(forms.Form):
    distance = forms.FloatField()
    pattern = forms.ChoiceField(choices=(('square','square'),('line','line')))
    record_gpr = forms.BooleanField()

    def send_req(self):
        data = self.cleaned_data

        requests.get('http://{}/start'.format(settings.ROBOT_API_ADDRESS), params=data)
        #return response.json()


class ScanListView(FormView):

    template_name = "frontend/scan_list.html"
    form_class = RoverForm
    success_url = '/'

    def form_valid(self, form):
        # This method is called when valid form data has been POSTed.
        # It should return an HttpResponse.
        form.send_req()
        return super().form_valid(form)

    def _get_scans(self):
        data = {}
        try:
            directories = next(os.walk(settings.SCAN_DATA_DIR))[1]
        except:
            import traceback; traceback.print_exc()
            directories = []

        for d in directories:
            if d == 'None':
                continue
            scan_path = os.path.join(settings.SCAN_DATA_DIR, d)
            result_path = os.path.join(settings.SCAN_DATA_DIR, d+'o')

            try:
                ts = datetime.datetime.strptime(d,"%Y-%m-%dT%H:%M:%S.%f")
            except:
                ts = ''

            data[d] = {'path': scan_path, 'samples': len(os.listdir(scan_path)),
                        'is_processed': os.path.exists(result_path),
                        'date': ts}
        return data


    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['scan_data'] = self._get_scans()
        #context['latest_articles'] = Article.objects.all()[:5]
        if self.request.GET.get('cancel'):
            requests.get('http://{}/cancel'.format(settings.ROBOT_API_ADDRESS))
        return context
