from django.shortcuts import render


def app_home(request):
    return render(request, 'dealerships/index.html')
