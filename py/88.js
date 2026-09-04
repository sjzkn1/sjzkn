var rule = {
    title: '幸福加油站',
    host: 'https://887717.xyz',
    url: '/fyclass/page/fypage/',
    searchUrl: '/page/fypage/?s=**',
    searchable: 2,
    quickSearch: 0,
    filterable: 0,
    headers: {
        'User-Agent': 'MOBILE_UA',
        'Referer': 'https://887717.xyz/'
    },
    class_name: '91&自拍&探花&日韩&网曝&欧美&裸聊&无码&FC2',
    class_url: '91大神&国产自拍&探花&ribenyouma&自拍泄露&欧美中字&美女裸聊&日本无码&fc2无码',
    play_parse: true,
    lazy: `js:
        let html = request(input);
        let m3u8 = html.match(/https?:\\/\\/[^"'\\s]+\\.m3u8[^"'\\s]*/);
        if (m3u8) {
            input = {parse: 0, url: m3u8[0], header: rule.headers};
        } else {
            let mp4 = html.match(/https?:\\/\\/[^"'\\s]+\\.mp4[^"'\\s]*/);
            if (mp4) {
                input = {parse: 0, url: mp4[0], header: rule.headers};
            } else {
                input = {parse: 1, url: input};
            }
        }
    `,
    limit: 24,
    推荐: '.video-block;a.infos&&title;img.video-img&&data-src;.views-number&&Text;a.thumb&&href',
    一级: '.video-block;a.infos&&title;img.video-img&&data-src;.views-number&&Text;a.thumb&&href',
    二级: '*',
    搜索: '.video-block;a.infos&&title;img.video-img&&data-src;.views-number&&Text;a.thumb&&href',
}
