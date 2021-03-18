from django.shortcuts import render

def index(request):
    context = {}
    return render(request, 'pages/index.html', context)

# Create your views here.
