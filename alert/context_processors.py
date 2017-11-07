def alert(request):
    if request.session.get('alert'):
        msg = request.session['alert']
        del request.session['alert']
        return {'alert': msg}
    return {}
