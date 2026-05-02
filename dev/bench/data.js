window.BENCHMARK_DATA = {
  "lastUpdate": 1777755089267,
  "repoUrl": "https://github.com/arthurvasconcelos/seedling",
  "entries": {
    "Benchmark": [
      {
        "commit": {
          "author": {
            "email": "vasconcelos.arthur@gmail.com",
            "name": "Arthur Vasconcelos",
            "username": "arthurvasconcelos"
          },
          "committer": {
            "email": "vasconcelos.arthur@gmail.com",
            "name": "Arthur Vasconcelos",
            "username": "arthurvasconcelos"
          },
          "distinct": true,
          "id": "c9c0df07e34a5a1535c3f8699cb3844f44817178",
          "message": "fix: benchmark CI — collect results in one step to avoid JSON parse errors",
          "timestamp": "2026-05-02T22:51:12+02:00",
          "tree_id": "14f3be04dc51690a3dc97d7e019025b7fb211d9e",
          "url": "https://github.com/arthurvasconcelos/seedling/commit/c9c0df07e34a5a1535c3f8699cb3844f44817178"
        },
        "date": 1777755088683,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "create_batch per-row 1000 rows",
            "value": 1.0704,
            "unit": "seconds"
          },
          {
            "name": "create_batch bulk 1000 rows",
            "value": 0.0958,
            "unit": "seconds"
          },
          {
            "name": "parallel 3 seeders",
            "value": 0.601,
            "unit": "seconds"
          },
          {
            "name": "sequential 3 seeders",
            "value": 0.6578,
            "unit": "seconds"
          }
        ]
      }
    ]
  }
}