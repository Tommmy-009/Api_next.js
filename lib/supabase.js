const { createClient } = require('@supabase/supabase-js');

const SUPABASE_URL = "https://zrnpreqpucgjpvnkffzm.supabase.co";
const SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InpybnByZXFwdWNnanB2bmtmZnptIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTA2MTM3MTksImV4cCI6MjA2NjE4OTcxOX0.eIzpRiyH-7N3QxB56Cy-ry-QnhTo6MeYfN_S4UVcOkI";

const supabase = createClient(SUPABASE_URL, SUPABASE_KEY);

module.exports = { supabase };