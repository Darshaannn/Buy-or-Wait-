from .utils import D, money, parse_date, read_csv

class FXTable:
    def __init__(self, path=None):
        self.rates={}
        if path:
            for r in read_csv(path):
                key=(parse_date(r['rate_date']),r['from_currency'],r['to_currency'])
                rate=D(r['rate'])
                if rate<=0: raise ValueError('Nonpositive FX rate')
                if key in self.rates and self.rates[key]!=rate: raise ValueError('Conflicting FX rate')
                self.rates[key]=rate

    def convert(self, amount, when, currency, home):
        if currency==home: return money(amount)
        key=(when,currency,home)
        if key not in self.rates: raise ValueError(f'Missing dated FX rate: {key}')
        return money(amount*self.rates[key])
