import { Injectable } from '@angular/core'
import { HttpClient } from '@angular/common/http'

@Injectable({
    providedIn: 'root'
})
export class AutocompletionService {
    private readonly countriesUrl =
        'https://countriesnow.space/api/v0.1/countries'
    private readonly currenciesUrl = 'https://restcountries.com/v3.1/all'

    constructor(private readonly http: HttpClient) {}

    getCountries() {
        return this.http.get(`${this.countriesUrl}`)
    }

    getCurrencies() {
        return this.http.get(`${this.currenciesUrl}`)
    }
}
