import { HttpClient } from '@angular/common/http'
import { Injectable } from '@angular/core'
import { Observable } from 'rxjs'
import { Payment } from '../../interfaces/payment'
import { environment } from '../../../environments/environment'

@Injectable({
    providedIn: 'root'
})
export class PaymentService {
    private readonly apiUrl = `${environment.serverUrl}`

    constructor(private readonly http: HttpClient) {}

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

    getAllPayments(): Observable<any> {
        return this.http.get(this.apiUrl)
    }

    getFilteredPayments(filters: any): Observable<any> {
        return this.http.post(`${this.apiUrl}/filter`, filters)
    }

    uploadEvidence(paymentId: string, formData: FormData): Observable<any> {
        return this.http.post(`${this.apiUrl}/upload/${paymentId}`, formData)
    }
    downloadEvidence(paymentId: string): Observable<any> {
        return this.http.get(`${this.apiUrl}/download/${paymentId}`, {
            responseType: 'blob'
        })
    }
}
