<script>
    $(document).ready(function() {
        luxon.Settings.defaultLocale = "{{LANGUAGE_CODE}}"; // Luxon autodetect seems broken
        function parse_time(data, type) {
            if (data == null) {
            return '-';
            }
            return DateTime.fromISO(data).toLocaleString(DateTime.DATETIME_MED);
        }
    
        $('.utc_date').each(function() {
            $(this).text(parse_time($(this).text(), null));
        });
    });
</script>