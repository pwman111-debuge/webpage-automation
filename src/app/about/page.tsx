
import React from 'react';
import Link from 'next/link';

export default function AboutPage() {
    return (
        <div className="max-w-4xl mx-auto py-12 px-4">
            <h1 className="text-3xl font-bold mb-8">서비스 소개</h1>

            <div className="prose prose-slate max-w-none space-y-8 text-muted-foreground">
                <section>
                    <h2 className="text-2xl font-bold text-foreground mb-4">제네시스 주식 리포트: 경험과 데이터가 만나는 한국 증시 인사이트</h2>
                    <p className="text-lg leading-relaxed">
                        제네시스 주식 리포트는 30년간 쌓아온 임상적 관찰력과 데이터 해석 경험을 바탕으로, 정밀한 AI 분석 시스템을 결합하여 탄생한 주식 분석 플랫폼입니다. 방대한 시장 데이터 속에서 의미 있는 신호를 포착하고, 개인 투자자들이 보다 냉철하고 현명한 의사결정을 내릴 수 있도록 돕습니다.
                    </p>
                </section>

                <section>
                    <h2 className="text-xl font-semibold text-foreground mb-3">운영 철학</h2>
                    <p className="leading-relaxed">
                        수십 년간 수많은 데이터를 분석하고 패턴을 읽어온 경험은 주식 시장에서도 그대로 적용됩니다. 감정이 아닌 데이터, 추측이 아닌 근거. 정교하게 설계된 AI 워크플로우가 시장의 수급·기술적 지표·거시 환경을 종합 분석하면, 그 결과를 오랜 투자 경험의 안목으로 한 번 더 검증합니다. 이것이 제네시스 리포트의 방식입니다.
                    </p>
                </section>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-6 my-10">
                    <div className="p-6 rounded-xl bg-accent/50 border border-border">
                        <h3 className="text-lg font-bold text-foreground mb-2">AI 기반 정밀 분석</h3>
                        <p>다단계 AI 워크플로우가 수급, 기술적 지표, 거시 환경을 동시에 분석하여 시장의 핵심 흐름을 빠르게 포착합니다.</p>
                    </div>
                    <div className="p-6 rounded-xl bg-accent/50 border border-border">
                        <h3 className="text-lg font-bold text-foreground mb-2">경험 기반 검증</h3>
                        <p>데이터 분석 결과를 다년간의 투자 경험으로 교차 검증하여 신뢰도 높은 인사이트를 제공합니다.</p>
                    </div>
                    <div className="p-6 rounded-xl bg-accent/50 border border-border">
                        <h3 className="text-lg font-bold text-foreground mb-2">실시간 시황 데이터</h3>
                        <p>국내외 핵심 지표와 시장의 주요 흐름을 실시간으로 추적하여 가장 빠르게 전달합니다.</p>
                    </div>
                    <div className="p-6 rounded-xl bg-accent/50 border border-border">
                        <h3 className="text-lg font-bold text-foreground mb-2">심층 종목 리포트</h3>
                        <p>재무제표 분석부터 성장성 평가까지, 다양한 각도에서 종목을 분석한 전문 리포트를 제공합니다.</p>
                    </div>
                </div>

                <section>
                    <h2 className="text-xl font-semibold text-foreground mb-3">우리의 미션</h2>
                    <p>
                        정보의 불균형을 해소하고, 전업 투자자와 일반 개인 투자자 모두가 전문가 수준의 데이터 분석을 활용할 수 있는 환경을 만드는 것이 제네시스 주식 리포트의 목표입니다.
                    </p>
                </section>

                <section className="bg-primary/5 p-8 rounded-2xl border border-primary/20 text-center">
                    <h2 className="text-xl font-semibold text-primary mb-4">연락처 및 피드백</h2>
                    <p className="mb-6">서비스 이용 관련 제안이나 비즈니스 문의는 전용 문의 폼을 이용해 주세요.</p>
                    <Link
                        href="/contact"
                        className="inline-block bg-primary text-white font-bold px-8 py-3 rounded-xl hover:bg-primary/90 transition-colors"
                    >
                        문의하기 페이지로 이동
                    </Link>
                </section>
            </div>
        </div>
    );
}
