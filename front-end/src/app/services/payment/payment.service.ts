import { HttpClient } from '@angular/common/http'
import { Injectable } from '@angular/core'
import { Observable } from 'rxjs'
import { Payment } from '../../interfaces/payment'

@Injectable({
    providedIn: 'root'
})
export class PaymentService {
    private readonly apiUrl = 'http://localhost:8000/payments'

    constructor(private readonly http: HttpClient) {}

    getPayments(filters: any, page: number, size: number): Observable<any> {
        return this.http.get(
            `${this.apiUrl}?filters=${JSON.stringify(
                filters
            )}&page=${page}&size=${size}`
        )
    }

    getPaymentById(id: string): Observable<any> {
        return this.http.get(`${this.apiUrl}/${id}`)
    }

    addPayment(payment: Payment): Observable<any> {
        return this.http.post(this.apiUrl, payment)
    }

    updatePayment(id: string, payment: Payment): Observable<any> {
        return this.http.put(`${this.apiUrl}/${id}`, payment)
    }

    deletePayment(id: string): Observable<any> {
        return this.http.delete(`${this.apiUrl}/${id}`)
    }
}
