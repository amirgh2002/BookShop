from django.http import Http404
from django.shortcuts import HttpResponse, render, redirect, get_object_or_404
from django.contrib.auth.models import User
from django.contrib import messages
from django.views import View
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from cart.cart import Cart
from .models import Order, OrderItem
from .forms import OrderCreateForm
from .pdfcreator import renderPdf
from django.urls import reverse
from azbankgateways import bankfactories, models as bank_models, default_settings as settings
import azbankgateways.exceptions as bank_exceptions # تغییر نام برای جلوگیری از تداخل

def order_create(request):
	cart = Cart(request)
	if request.user.is_authenticated:
		customer = get_object_or_404(User, id=request.user.id)
		form = OrderCreateForm(request.POST or None, initial={"name": customer.first_name, "email": customer.email})
		
		if request.method == 'POST':
			if form.is_valid():
				order = form.save(commit=False)
				order.customer = User.objects.get(id=request.user.id)
				order.payable = cart.get_total_price() # مبلغ کل (فرض می‌کنیم به تومان است)
				order.totalbook = len(cart)
				# ✅ سفارش ذخیره می‌شود اما هنوز پرداخت نشده (paid=False)
				order.save()

				for item in cart:
					OrderItem.objects.create(
						order=order, 
						book=item['book'], 
						price=item['price'], 
						quantity=item['quantity']
						)
				
				# ✅ بخش جدید: هدایت به سمت درگاه پرداخت
				# آیدی سفارش را در سشن ذخیره می‌کنیم تا در بازگشت از بانک آن را بازیابی کنیم
				request.session['order_id'] = order.id

				try:
					bank = bankfactories.BankFactory().create()
					# نام درگاهی که در settings.py تنظیم کردید
					bank.set_merchant_code('ZARINPAL') 
					bank.set_amount(order.payable)
					# توضیحات پرداخت (در پنل زرین‌پال نمایش داده می‌شود)
					bank.set_description(f"سفارش شماره #{order.id} از فروشگاه کتاب") 
					bank.set_mobile_number(order.phone)

					# آدرس بازگشتی که در urls.py ساختیم
					bank.set_callback_url(reverse('order:payment_callback'))
					
					# دریافت رکورد بانک و ارسال کاربر به گیت‌وی
					bank_record = bank.go_to_gateway_view()
					
					# هدایت کاربر به صفحه بانک
					return bank.redirect_to_gateway()

				except bank_exceptions.BankGatewayExceptions as e:
					messages.error(request, f"خطا در اتصال به درگاه پرداخت: {e}")
					# در صورت بروز خطا، سفارش و آیتم‌های آن را پاک می‌کنیم تا دوباره تلاش کند
					order.delete() 
					return redirect('cart:cart_details')

			else:
				messages.error(request, "Fill out your information correctly.")

		if len(cart) > 0:
			return render(request, 'order/order.html', {"form": form})
		else:
			return redirect('store:books')
	else:
		return redirect('store:signin')

#
# ✅ تابع جدید: مدیریت بازگشت از درگاه پرداخت
#
def payment_callback(request):
	# شناسه سفارشی که در سشن ذخیره کرده بودیم را می‌خوانیم
	order_id = request.session.get('order_id')
	if not order_id:
		messages.error(request, "خطا: شناسه سفارش شما یافت نشد.")
		return redirect('store:books')

	order = get_object_or_404(Order, id=order_id)
	cart = Cart(request)

	try:
		bank = bankfactories.BankFactory().create()
		# مبلغ را برای تایید مجدد تنظیم می‌کنیم
		bank.set_amount(order.payable)
		bank.set_merchant_code('ZARINPAL')

		# کد رهگیری را از URL می‌خوانیم
		tracking_code = bank.get_tracking_code_from_request(request)

		# پرداخت را تایید می‌کنیم
		is_paid, bank_record = bank.verify_payment_view(tracking_code, request)

		if is_paid:
			# ✅ پرداخت موفق بود!
			# اطلاعات را در دیتابیس ذخیره می‌کنیم
			order.paid = True
			order.transaction_id = bank_record.tracking_code  # ذخیره کد رهگیری زرین‌پال
			order.save()
			
			# سبد خرید را خالی می‌کنیم
			cart.clear()
			# شناسه سفارش را از سشن پاک می‌کنیم
			del request.session['order_id']
			
			# کاربر را به همان صفحه موفقیت‌آمیز قبلی هدایت می‌کنیم
			return render(request, 'order/successfull.html', {'order': order})
		else:
			# پرداخت ناموفق بود
			# پیام خطای بانک را نمایش می‌دهیم
			messages.error(request, bank_record.response_result or "پرداخت ناموفق بود.")
			return redirect('cart:cart_details') # بازگشت به سبد خرید

	except bank_exceptions.BankGatewayExceptions as e:
		messages.error(request, f"خطا در پردازش پرداخت: {e}")
		return redirect('cart:cart_details')
			
def order_list(request):
	my_order = Order.objects.filter(customer_id = request.user.id).order_by('-created')
	paginator = Paginator(my_order, 5)
	page = request.GET.get('page')
	myorder = paginator.get_page(page)

	return render(request, 'order/list.html', {"myorder": myorder})

def order_details(request, id):
	order_summary = get_object_or_404(Order, id=id)

	if order_summary.customer_id != request.user.id:
		return redirect('store:index')

	orderedItem = OrderItem.objects.filter(order_id=id)
	context = {
		"o_summary": order_summary,
		"o_item": orderedItem
	}
	return render(request, 'order/details.html', context)

class pdf(View):
    def get(self, request, id):
        try:
            query=get_object_or_404(Order,id=id)
        except:
            Http404('Content not found')
        context={
            "order":query
        }
        article_pdf = renderPdf('order/pdf.html',context)
        return HttpResponse(article_pdf,content_type='application/pdf')
