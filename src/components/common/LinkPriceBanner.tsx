const banners = [
  {
    href: 'https://click.linkprice.com/click.php?m=mycredit1&a=A100704068&l=yPxP&u_id=',
    src: 'https://img.credit.co.kr/resource/img/linkprice/20230112/C_728x90.jpg',
    track: 'https://track.linkprice.com/lpshow.php?m_id=mycredit1&a_id=A100704068&p_id=0000&l_id=yPxP&l_cd1=2&l_cd2=0',
  },
  {
    href: 'https://click.linkprice.com/click.php?m=mycredit1&a=A100704068&l=Qswu&u_id=',
    src: 'https://img.credit.co.kr/resource/img/linkprice/20230112/B_728x90.jpg',
    track: 'https://track.linkprice.com/lpshow.php?m_id=mycredit1&a_id=A100704068&p_id=0000&l_id=Qswu&l_cd1=2&l_cd2=0',
  },
  {
    href: 'https://click.linkprice.com/click.php?m=mycredit1&a=A100704068&l=yBsf&u_id=',
    src: 'https://img.credit.co.kr/resource/img/linkprice/20230112/A_728x90.jpg',
    track: 'https://track.linkprice.com/lpshow.php?m_id=mycredit1&a_id=A100704068&p_id=0000&l_id=yBsf&l_cd1=2&l_cd2=0',
  },
];

export function LinkPriceBanner({ index = 0 }: { index?: number }) {
  const banner = banners[index % banners.length];
  return (
    <div className="w-full flex justify-center my-4 overflow-hidden">
      <a target="_blank" rel="noopener noreferrer" href={banner.href}>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={banner.src} width={728} height={90} alt="광고" style={{ maxWidth: '100%', height: 'auto' }} />
      </a>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={banner.track} width={1} height={1} alt="" style={{ display: 'none' }} />
    </div>
  );
}
