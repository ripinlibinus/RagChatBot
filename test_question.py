def question():
    QUESTIONS = [
        {
            "id" : 1,
            "q" : "Carikan rumah dijual di daerah cemara",
            "gold"  :{
                "keyword": "cemara", 
                "tipe_listing": 1, 
                "jenis_properti": 1, 
                "page": 1,
            }
            
        },
        { 
            "id" : 2,
            "q": "Carikan rumah dijual di daerah ringroad",
            "gold"  : { 
                "keyword": "ringroad", 
                "tipe_listing": 1, 
                "jenis_properti": 1, 
                "page": 1,
            } 
        },
        { 
            "id" : 3,
            "q": "Carikan rumah sewa di medan",
            "gold": { 
                "keyword": "medan", 
                "tipe_listing": 2, 
                "jenis_properti": 1, 
                "page": 1, 
            } 
        },
        { 
            "id" : 4,
            "q": "Carikan rumah dijual di daerah cemara harga 1M an",
            "gold": { 
                "keyword": "cemara", 
                "harga_min": 800_000_000, 
                "harga_max": 1_200_000_000,
                "tipe_listing": 1, 
                "jenis_properti": 1, 
                "page": 1
            } 
        },
        { "id" : 5,
        "q" : "Carikan rumah dijual daerah ringroad harga dibawah 800juta 3 kamar", 
        "gold" :{ "keyword" : "ringroad",  "harga_max" : 800000000, "kamar_tidur" : 3,
                    "tipe_listing" : 1, "jenis_properti" : 1, "page" : 1 } },
        { "id" : 6,
        "q": "apakah ada rumah sewa di medan yang dibawah 50juta 3 kamar?",
        "gold": { "keyword": "medan", "harga_max": 50_000_000, "kamar_tidur": 3,
                    "tipe_listing": 2, "jenis_properti": 1, "page": 1, "paginate": 5 } },

        { "id" : 7,
        "q": "Saya ingin beli rumah di dekat podomoro medan harga dibawah 1M ada?",
        "gold": { "keyword": "podomoro", "harga_max": 1_000_000_000,
                    "tipe_listing": 1, "jenis_properti": 1, "page": 1, "paginate": 5 } },
        { "id" : 8,
        "q": "Client saya lagi cari sewa dekat usu, anaknya mau kuliah disana",
        "gold": { "keyword": "usu", "tipe_listing": 2, "jenis_properti": 1, "page": 1, "paginate": 5 } },

        
        { "id" : 9,
        "q": "Carikan rumah di inti kota medan yang harganya dibawah 1M",
        "gold": { "keyword": "inti kota medan", "harga_max": 1_000_000_000,
                    "tipe_listing": 1, "jenis_properti": 1, "page": 1, "paginate": 5 } },

        { "id" : 10,
        "q": "apakah ada ruko yang disewakan di daerah krakatau?",
        "gold": { "keyword": "krakatau", "tipe_listing": 2, "jenis_properti": 2, "page": 1, "paginate": 5 } },

        { "id" : 11,
        "q": "saya lagi cari tanah yang dijual di marelan",
        "gold": { "keyword": "marelan", "tipe_listing": 1, "jenis_properti": 3, "page": 1, "paginate": 5 } },

        { "id" : 12,
        "q": "apakah ada gudang yang dijual atau disewa di KIM ?",
        "gold": { "keyword": "kim", "jenis_properti": 5, "page": 1, "paginate": 5 } },

        { "id" : 13,
        "q": "Carikan rumah dijual daerah ringroad  harga 1M an 3 kamar",
        "gold": { "keyword": "ringroad", "harga_min": 800_000_000, "harga_max": 1_200_000_000,
                    "kamar_tidur": 3, "tipe_listing": 1, "jenis_properti": 1, "page": 1, "paginate": 5 } },

        { "id" : 14,
        "q": "Apakah masih ada pilihan lain?",
        "gold": { "keyword": "ringroad", "harga_min": 800_000_000, "harga_max": 1_200_000_000,
                    "kamar_tidur": 3, "tipe_listing": 1, "jenis_properti": 1, "page": 2, "paginate": 5 } },

        { "id" : 15,
        "q": "Berikan lagi pilihan lain",
        "gold": { "keyword": "ringroad", "harga_min": 800_000_000, "harga_max": 1_200_000_000,
                    "kamar_tidur": 3, "tipe_listing": 1, "jenis_properti": 1, "page": 3, "paginate": 5 } },

        { "id" : 16,
        "q": "kasih pilihan lain, lokasi dan harga masih sama, tapi yang 3 lantai?",
        "gold": { "keyword": "ringroad", "harga_min": 800_000_000, "harga_max": 1_200_000_000,
                    "kamar_tidur": 3, "tipe_listing": 1, "jenis_properti": 1, "jumlah_tingkat": 3, "page": 1, "paginate": 5 } },

        { "id" : 17,
        "q": "Berikan lagi pilihan lain",
        "gold": { "keyword": "ringroad", "harga_min": 800_000_000, "harga_max": 1_200_000_000,
                    "kamar_tidur": 3, "tipe_listing": 1, "jenis_properti": 1, "jumlah_tingkat": 3, "page": 2, "paginate": 5 } },

        { "id" : 18,
        "q": "Kalau pilihan lain, lokasi dan jumlah lantai masih sama, tapi yang dibawah 800 juta ada?",
        "gold": { "keyword": "ringroad", "harga_max": 800_000_000,
                    "kamar_tidur": 3, "tipe_listing": 1, "jenis_properti": 1, "jumlah_tingkat": 3, "page": 1, "paginate": 5 } },

        { "id" : 19,
        "q": "carikan rumah dengan fasilitas cctv di medan",
        "gold": { "keyword": "medan", "info_lainnya":"cctv" } },

        { "id" : 20,
        "q": "carikan rumah dengan fasilitas wifi di medan",
        "gold": { "keyword": "medan", "info_lainnya":"wifi" } },

        { "id" : 21,
        "q": "cari rumah dalam komplek dengan fasilitas lapangan basket",
        "gold": { "info_lainnya":"basket" } },

        { "id" : 22,
        "q": "cari rumah yang bisa parkir beberapa mobil",
        "gold": { "info_lainnya":"parkir" } },

        { "id" : 23,
        "q": "cari rumah yang sudah ada ac, lemari, dapur dan tangki air",
        "gold": { "info_lainnya":"tangki air" } },

        { "id" : 24,
        "q": "cari rumah dekat mall",
        "gold": { "info_lainnya":"mall" } },

        { "id" : 25,
        "q": "cari rumah dekat sekolah di medan",
        "gold": { "info_lainnya":"sekolah" } },

        
        { "id" : 26,
        "q": "cari rumah dekat mall yang harganya dibawah 800 juta",
        "gold": { "info_lainnya":"mall", "harga_max": 800_000_000 } },

        { "id" : 27,
        "q": "cari rumah full furnished yang harganya dibawah 1 M dalam komplek dengan fasilitas lapangan basket",
        "gold": { "info_lainnya":"basket", "harga_max": 1_000_000_000 } },

        { "id" : 28,
        "q": "cari apartment di podomoro yang bisa harganya dibawah 1.5 M",
        "gold": { "keyword": "podomoro","harga_max": 1_500_000_000 } },

        { "id" : 29,
        "q": "cari rumah di citraland bagya city medan ",
        "gold": { "keyword": "citraland bagya city" } },

        { "id" : 30,
        "q": "cari rumah dijual di komplek givency one",
        "gold": { "keyword": "givency one", "tipe_listing": 1, "jenis_properti": 1} },
    ]
    return QUESTIONS