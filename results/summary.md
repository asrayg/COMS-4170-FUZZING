# Graylayer Fuzzing — Results Summary

- Total recorded events: **2,533**
- Services exercised: **gateway**
- Unique endpoints exercised: **51**

## Events by service
| service   |   events |
|:----------|---------:|
| gateway   |     2533 |

## Events by severity
| severity   |   events |
|:-----------|---------:|
| medium     |     1339 |
| info       |     1169 |
| high       |       19 |
| low        |        6 |

## Events by category
| category                   |   events |
|:---------------------------|---------:|
| unexpected                 |     1224 |
| client_error               |     1129 |
| transport                  |      114 |
| negative:client_error      |       17 |
| invariant                  |       15 |
| ok                         |       13 |
| negative:ok                |       10 |
| negative:unexpected_status |        6 |
| contract                   |        2 |
| crash                      |        1 |
| negative:crash             |        1 |
| timeout                    |        1 |

## Status code distribution
|   status |   events |
|---------:|---------:|
|      200 |     1042 |
|      400 |      204 |
|      403 |        4 |
|      404 |     1276 |
|      414 |        1 |
|      500 |        2 |
|      nan |        4 |

## High-severity findings by endpoint
| service   | endpoint                                      | category       |   count |
|:----------|:----------------------------------------------|:---------------|--------:|
| gateway   | /api/v1/polymarket-us/markets/{id}            | invariant      |       5 |
| gateway   | /api/v1/polymarket-us/markets/{slug}          | invariant      |       5 |
| gateway   | /api/v1/polymarket-us/events/{slug}           | invariant      |       3 |
| gateway   | /api/v1/coinbase/products/{product_id}/ticker | invariant      |       2 |
| gateway   | /api/v1/gemini/v1/trades/BTCUSD               | negative:crash |       1 |
| gateway   | /api/v1/gemini/v2/ticker/{symbol}             | contract       |       1 |
| gateway   | /api/v1/kalshi/markets                        | crash          |       1 |
| gateway   | /api/v1/polymarket-us/events/{id}             | contract       |       1 |

## Top 20 non-OK endpoints
| service   | endpoint                                           | severity   |   count |
|:----------|:---------------------------------------------------|:-----------|--------:|
| gateway   | /api/v1/kalshi/markets/trades                      | medium     |      75 |
| gateway   | /api/v1/gemini/v1/prediction-markets/events        | medium     |      75 |
| gateway   | /api/v1/kalshi/events                              | medium     |      75 |
| gateway   | /api/v1/kalshi/exchange/status                     | medium     |      75 |
| gateway   | /api/v1/kalshi/series                              | medium     |      75 |
| gateway   | /api/v1/polymarket-us/events                       | medium     |      75 |
| gateway   | /api/v1/polymarket-us/markets                      | medium     |      75 |
| gateway   | /api/v1/polymarket-us/markets/{slug}/book          | info       |      75 |
| gateway   | /api/v1/coinbase/products/{product_id}/trades      | medium     |      75 |
| gateway   | /api/v1/polymarket-us/partners/events/{externalId} | info       |      75 |
| gateway   | /api/v1/polymarket-us/search                       | medium     |      75 |
| gateway   | /api/v1/coinbase/products/{product_id}/candles     | medium     |      75 |
| gateway   | /api/v1/polymarket-us/series                       | medium     |      75 |
| gateway   | /api/v1/polymarket-us/sports                       | medium     |      75 |
| gateway   | /api/v1/polymarket-us/sports/teams                 | medium     |      75 |
| gateway   | /api/v1/gemini/v1/prediction-markets/categories    | medium     |      75 |
| gateway   | /api/v1/coinbase/products/{product_id}/book        | info       |      73 |
| gateway   | /api/v1/coinbase/products/{product_id}/ticker      | info       |      72 |
| gateway   | /api/v1/polymarket-us/markets/{slug}/settlement    | info       |      72 |
| gateway   | /api/v1/polymarket-us/markets/{id}                 | info       |      72 |

## Representative high-severity cases (first 5)
| service   | endpoint                             | method   |   status | category   | error                                                                              | query   | path_params                            |
|:----------|:-------------------------------------|:---------|---------:|:-----------|:-----------------------------------------------------------------------------------|:--------|:---------------------------------------|
| gateway   | /api/v1/polymarket-us/markets/{id}   | GET      |      404 | invariant  | market id '1' from list returned 404 on detail endpoint                            |         | {'id': '1'}                            |
| gateway   | /api/v1/polymarket-us/markets/{slug} | GET      |      404 | invariant  | market slug 'aec-nfl-lac-ten-2025-11-02' from list returned 404 on detail endpoint |         | {'slug': 'aec-nfl-lac-ten-2025-11-02'} |
| gateway   | /api/v1/polymarket-us/markets/{id}   | GET      |      404 | invariant  | market id '2' from list returned 404 on detail endpoint                            |         | {'id': '2'}                            |
| gateway   | /api/v1/polymarket-us/markets/{slug} | GET      |      404 | invariant  | market slug 'aec-nfl-car-gb-2025-11-02' from list returned 404 on detail endpoint  |         | {'slug': 'aec-nfl-car-gb-2025-11-02'}  |
| gateway   | /api/v1/polymarket-us/markets/{id}   | GET      |      404 | invariant  | market id '3' from list returned 404 on detail endpoint                            |         | {'id': '3'}                            |
