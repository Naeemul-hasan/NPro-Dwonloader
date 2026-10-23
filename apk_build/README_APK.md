# 📱 NPro Downloader — Android APK বিল্ড করার সম্পূর্ণ নির্দেশিকা

NPro Downloader সম্পূর্ণ আধুনিক রেসপনসিভ UI আর্কিটেকচারে তৈরি, যা মোবাইল ডিভাইসে অসাধারণ প্রিমিয়াম গ্লাসমরফিজম অনুভূতি প্রদান করে।

---

### পদ্ধতি ১: ক্লাউড অটোমেশন (কোনো SDK ইন্সটল ছাড়া সবচেয়ে সহজ)
এই প্রজেক্টটিতে **GitHub Actions CI/CD Workflow** যুক্ত করা আছে:
1. প্রজেক্টটি আপনার GitHub রিপোজিটরিতে আপলোড করুন (`git push`)।
2. `.github/workflows/` ফোল্ডারে `apk_build/android_build_workflow.yml` ফাইলটি রাখুন।
3. GitHub-এর **Actions** ট্যাবে যান এবং `Build NPro Downloader Android APK` রান করুন।
4. মাত্র ২ মিনিটের মধ্যে GitHub স্বয়ংক্রিয়ভাবে একটি রেডি-টু-ইন্সটল `NPro-Downloader.apk` ফাইল তৈরি করে দেবে, যা সরাসরি মোবাইলে ডাউনলোড করে ইন্সটল করা যাবে!

---

### পদ্ধতি ২: লোকাল কম্পিউটারে Capacitor দিয়ে APK বিল্ড (CLI)
আপনার কম্পিউটারে Node.js ও Android Studio থাকলে:
```bash
cd apk_build
npm init -y
npm install @capacitor/core @capacitor/cli @capacitor/android
npx cap add android
npx cap sync android
npx cap open android
```
এরপর Android Studio ওপেন হলে **Build > Build Bundle(s) / APK(s) > Build APK(s)** ক্লিক করলেই `.apk` তৈরি হয়ে যাবে।

---

### পদ্ধতি ৩: PWA (Instant Mobile App - নো কম্পাইলেশন)
যেহেতু NPro Downloader-এ ফুল `manifest.json` এবং `ServiceWorker (sw.js)` যুক্ত রয়েছে:
1. আপনার লোকাল নেটওয়ার্কে বা ইন্টারনেটে হোস্ট করা NPro Downloader-এর লিঙ্কে অ্যান্ড্রয়েড ক্রোমে ঢুকুন।
2. ক্রোমের মেনুতে থাকা **"Add to Home Screen"** বা **"Install App"** ক্লিক করুন।
3. এটি সাথে সাথে মোবাইলে একটি স্বতন্ত্র নেটিভ অ্যাপের মতো আইকনসহ ইন্সটল হয়ে যাবে এবং ফুলস্ক্রিন অ্যাপ আকারে চলবে!
