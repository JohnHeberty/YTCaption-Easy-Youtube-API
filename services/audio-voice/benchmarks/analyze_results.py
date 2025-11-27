"""
Análise de Resultados - Benchmark XTTS vs F5-TTS

Analisa métricas quantitativas e MOS scores, gerando relatório comparativo.

Usage:
    python analyze_results.py
    python analyze_results.py --metrics results/metrics.csv
"""

import argparse
import pandas as pd
import numpy as np
from pathlib import Path
from scipy import stats
import json


class BenchmarkAnalyzer:
    """Analisa resultados do benchmark"""
    
    def __init__(self, metrics_path: str = "results/metrics.csv"):
        self.metrics_path = Path(metrics_path)
        
        if not self.metrics_path.exists():
            raise FileNotFoundError(f"Metrics file not found: {self.metrics_path}")
        
        self.df = pd.read_csv(self.metrics_path)
        
        print(f"\n{'='*80}")
        print("📊 ANÁLISE DE RESULTADOS - XTTS vs F5-TTS")
        print(f"{'='*80}\n")
        print(f"Métricas carregadas: {len(self.df)} amostras")
        print(f"Engines: {self.df['engine'].unique().tolist()}")
        print()
    
    def analyze_performance(self):
        """Analisa métricas de performance"""
        print(f"{'='*80}")
        print("⚡ ANÁLISE DE PERFORMANCE")
        print(f"{'='*80}\n")
        
        for engine in self.df['engine'].unique():
            engine_df = self.df[self.df['engine'] == engine]
            
            print(f"🔹 {engine.upper()}")
            print(f"   Amostras: {len(engine_df)}")
            print(f"   RTF médio: {engine_df['rtf'].mean():.3f}x (±{engine_df['rtf'].std():.3f})")
            print(f"   RTF min/max: {engine_df['rtf'].min():.3f}x / {engine_df['rtf'].max():.3f}x")
            print(f"   Tempo proc. médio: {engine_df['processing_time'].mean():.2f}s")
            print(f"   Memória média: {engine_df['memory_delta_mb'].mean():.1f}MB (±{engine_df['memory_delta_mb'].std():.1f})")
            print(f"   Duração áudio média: {engine_df['audio_duration'].mean():.2f}s")
            print()
        
        # Comparação estatística
        if len(self.df['engine'].unique()) == 2:
            xtts_rtf = self.df[self.df['engine'] == 'xtts']['rtf']
            f5tts_rtf = self.df[self.df['engine'] == 'f5tts']['rtf']
            
            # t-test
            t_stat, p_value = stats.ttest_ind(xtts_rtf, f5tts_rtf)
            
            print(f"📈 Comparação Estatística (RTF):")
            print(f"   t-statistic: {t_stat:.4f}")
            print(f"   p-value: {p_value:.4f}")
            
            if p_value < 0.05:
                print(f"   ✅ Diferença SIGNIFICATIVA (p < 0.05)")
                if xtts_rtf.mean() < f5tts_rtf.mean():
                    print(f"   → XTTS é significativamente mais rápido")
                else:
                    print(f"   → F5-TTS é significativamente mais rápido")
            else:
                print(f"   ℹ️  Diferença NÃO significativa (p >= 0.05)")
            print()
    
    def analyze_by_category(self):
        """Analisa performance por categoria de texto"""
        print(f"{'='*80}")
        print("📋 ANÁLISE POR CATEGORIA")
        print(f"{'='*80}\n")
        
        categories = self.df['text_category'].unique()
        
        for category in categories:
            cat_df = self.df[self.df['text_category'] == category]
            
            print(f"🔹 {category.upper()}")
            
            for engine in cat_df['engine'].unique():
                engine_cat_df = cat_df[cat_df['engine'] == engine]
                
                print(f"   {engine}: RTF={engine_cat_df['rtf'].mean():.3f}x, "
                      f"Duration={engine_cat_df['audio_duration'].mean():.2f}s")
            print()
    
    def generate_summary_report(self):
        """Gera relatório resumido em texto"""
        report_path = self.metrics_path.parent.parent / "reports" / "summary.txt"
        report_path.parent.mkdir(exist_ok=True, parents=True)
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write("="*80 + "\n")
            f.write("RELATÓRIO BENCHMARK - XTTS vs F5-TTS PT-BR\n")
            f.write("="*80 + "\n\n")
            
            f.write("1. RESUMO EXECUTIVO\n")
            f.write("-" * 80 + "\n")
            f.write(f"Total de amostras: {len(self.df)}\n")
            f.write(f"Engines comparados: {', '.join(self.df['engine'].unique())}\n")
            f.write(f"Categorias testadas: {', '.join(self.df['text_category'].unique())}\n\n")
            
            f.write("2. MÉTRICAS DE PERFORMANCE\n")
            f.write("-" * 80 + "\n")
            
            for engine in self.df['engine'].unique():
                engine_df = self.df[self.df['engine'] == engine]
                
                f.write(f"\n{engine.upper()}:\n")
                f.write(f"  RTF médio: {engine_df['rtf'].mean():.3f}x\n")
                f.write(f"  Tempo processamento: {engine_df['processing_time'].mean():.2f}s\n")
                f.write(f"  Memória: {engine_df['memory_delta_mb'].mean():.1f}MB\n")
            
            f.write("\n3. RECOMENDAÇÕES\n")
            f.write("-" * 80 + "\n")
            
            xtts_rtf = self.df[self.df['engine'] == 'xtts']['rtf'].mean()
            f5tts_rtf = self.df[self.df['engine'] == 'f5tts']['rtf'].mean()
            
            if xtts_rtf < f5tts_rtf:
                f.write(f"• XTTS é {f5tts_rtf/xtts_rtf:.2f}x mais rápido (melhor para produção)\n")
                f.write(f"• F5-TTS pode ter melhor qualidade (avaliar MOS scores)\n")
            else:
                f.write(f"• F5-TTS é {xtts_rtf/f5tts_rtf:.2f}x mais rápido\n")
                f.write(f"• Verificar qualidade via MOS testing\n")
            
            f.write("\n" + "="*80 + "\n")
        
        print(f"✅ Relatório salvo em: {report_path}\n")
        
        return str(report_path)
    
    def print_recommendations(self):
        """Imprime recomendações finais"""
        print(f"{'='*80}")
        print("💡 RECOMENDAÇÕES")
        print(f"{'='*80}\n")
        
        xtts_df = self.df[self.df['engine'] == 'xtts']
        f5tts_df = self.df[self.df['engine'] == 'f5tts']
        
        print("📌 Quando usar XTTS:")
        print("   • Quando velocidade é crítica (RTF < 1.0)")
        print("   • Quando VRAM é limitada")
        print("   • Quando backward compatibility é necessária")
        
        print("\n📌 Quando usar F5-TTS:")
        print("   • Quando qualidade/naturalidade é prioridade")
        print("   • Quando ref_text está disponível (melhor cloning)")
        print("   • Para conteúdo longo (melhor prosódia)")
        
        print("\n📌 Próximos passos:")
        print("   1. Coletar MOS scores (avaliar qualidade perceptual)")
        print("   2. Testar em casos de uso reais")
        print("   3. Avaliar trade-offs: velocidade vs qualidade")
        print()


def main():
    parser = argparse.ArgumentParser(description="Analisar resultados do benchmark")
    parser.add_argument(
        '--metrics',
        type=str,
        default='results/metrics.csv',
        help='Path para metrics.csv'
    )
    
    args = parser.parse_args()
    
    try:
        analyzer = BenchmarkAnalyzer(args.metrics)
        
        # Análises
        analyzer.analyze_performance()
        analyzer.analyze_by_category()
        
        # Relatório
        report_path = analyzer.generate_summary_report()
        
        # Recomendações
        analyzer.print_recommendations()
        
        print("="*80)
        print("✅ Análise completa!")
        print(f"\nRelatório disponível em: {report_path}")
        print("="*80 + "\n")
    
    except FileNotFoundError as e:
        print(f"❌ Erro: {e}")
        print("\nExecute primeiro: python run_benchmark.py")
    except Exception as e:
        print(f"❌ Erro inesperado: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
