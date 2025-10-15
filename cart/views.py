from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from store.models import Book, Category
from .cart import Cart
from django.http import JsonResponse 

def cart_add(request, bookid):
	cart = Cart(request)  
	book = get_object_or_404(Book, id=bookid) 
	cart.add(book=book)

	return redirect('store:index')

def cart_update(request):
	    # 1. دریافت اطلاعات از پارامترهای GET که با AJAX ارسال شده
    book_id = request.GET.get('book_id')
    # مقدار quantity که از AJAX می‌آید، رشته است، پس باید به عدد صحیح تبدیل شود
    quantity = int(request.GET.get('quantity'))

    # 2. به‌روزرسانی سبد خرید
    cart = Cart(request) 
    book = get_object_or_404(Book, id=book_id) 
    cart.add(book=book, quantity=quantity) # فرض بر این است که متد add شما quantity را هم می‌پذیرد
    
    # 3. محاسبه قیمت کل جدید برای همان محصول
    # (قیمت کتاب * تعداد جدید)
    total_price = book.price * quantity

    # 4. ارسال یک پاسخ JSON به AJAX
    # این همان چیزی است که success: function(data) در جاوااسکریپت شما دریافت می‌کند
    return JsonResponse({'total_price': total_price})



def cart_remove(request, bookid):
    cart = Cart(request)
    book = get_object_or_404(Book, id=bookid)
    cart.remove(book)
    return redirect('cart:cart_details')

def total_cart(request):
	return render(request, 'cart/totalcart.html')

def cart_summary(request):

	return render(request, 'cart/summary.html')

def cart_details(request):
	cart = Cart(request)
	context = {
		"cart": cart,
	}
	return render(request, 'cart/cart.html', context)

