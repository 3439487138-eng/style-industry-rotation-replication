import pandas as pd
import numpy as np
import statsmodels.api as sm
import os
from typing import List, Dict

class AlphaCalculator:
    """阿尔法计算器 - 多因子回归模型"""
    
    def __init__(self, mongo_uri=None, db_name=None):
        self.mongo_uri = mongo_uri or os.environ.get('PANDA_FACTOR_MONGO_URI')
        self.db_name = db_name or os.environ.get('PANDA_FACTOR_MONGO_DB', 'panda_factor')
        if not self.mongo_uri:
            raise ValueError('PANDA_FACTOR_MONGO_URI is required for the legacy AlphaCalculator')
    
    def calculate_alpha(
        self,
        stock_list: List[str],
        start_date: str,
        end_date: str,
        weights: List[float] = None
    ) -> Dict:
        """
        计算组合阿尔法
        
        公式：R_p - R_f = β_m(R_m - R_f) + Σβ_s*Style_s + Σβ_i*Industry_i + α
        """
        # 1. 获取数据
        portfolio_returns = self._get_portfolio_returns(stock_list, start_date, end_date, weights)
        market_returns = self._get_market_returns(start_date, end_date)
        risk_free = self._get_risk_free_rate(start_date, end_date)
        style_factors = self._get_style_factors(stock_list, start_date, end_date)
        industry_factors = self._get_industry_factors(stock_list)
        
        # 2. 构建回归数据
        df = pd.DataFrame({
            'date': portfolio_returns.index
        })
        df['portfolio_return'] = portfolio_returns.values
        df['market_return'] = market_returns.reindex(df['date']).values
        df['risk_free'] = risk_free.reindex(df['date']).values
        
        # 3. 计算超额收益
        df['excess_return'] = df['portfolio_return'] - df['risk_free']
        df['market_excess'] = df['market_return'] - df['risk_free']
        
        # 4. 构建因子矩阵
        X = pd.DataFrame()
        X['market'] = df['market_excess']
        
        # 添加风格因子
        for factor in style_factors.columns:
            X[factor] = style_factors[factor].reindex(df['date']).values
        
        # 添加行业因子
        industry_dummies = pd.get_dummies(industry_factors, prefix='ind')
        for col in industry_dummies.columns:
            X[col] = industry_dummies[col].values
        
        # 5. 执行回归
        X = sm.add_constant(X)
        y = df['excess_return']
        
        model = sm.OLS(y, X, missing='drop')
        results = model.fit()
        
        # 6. 返回结果
        return {
            'alpha': results.params['const'],
            'alpha_tstat': results.tvalues['const'],
            'alpha_pvalue': results.pvalues['const'],
            'beta_market': results.params['market'],
            'r_squared': results.rsquared,
            'regression_summary': results.summary()
        }
    
    def _get_portfolio_returns(self, stock_list, start_date, end_date, weights):
        """获取组合收益率 - 从 MongoDB 读取"""
        from pymongo import MongoClient
        client = MongoClient(self.mongo_uri)
        db = client[self.db_name]
        
        returns_list = []
        for stock in stock_list:
            data = list(db['stock_returns'].find({
                'ts_code': stock,
                'trade_date': {'$gte': int(start_date), '$lte': int(end_date)}
            }))
            if data:
                df = pd.DataFrame(data)
                df.set_index('trade_date', inplace=True)
                returns_list.append(df['pct_chg'] / 100)
        
        client.close()
        
        if weights is None:
            weights = [1.0 / len(returns_list)] * len(returns_list)
        
        portfolio_returns = sum(w * r for w, r in zip(weights, returns_list))
        return portfolio_returns
    
    def _get_market_returns(self, start_date, end_date):
        """获取市场收益率 - 沪深 300"""
        from pymongo import MongoClient
        client = MongoClient(self.mongo_uri)
        db = client[self.db_name]
        
        data = list(db['index_returns'].find({
            'ts_code': '000300.SH',
            'trade_date': {'$gte': int(start_date), '$lte': int(end_date)}
        }))
        
        client.close()
        
        if data:
            df = pd.DataFrame(data)
            df.set_index('trade_date', inplace=True)
            return df['pct_chg'] / 100
        return pd.Series()
    
    def _get_risk_free_rate(self, start_date, end_date):
        """获取无风险利率 - 简化为年化 3% 日化"""
        dates = pd.date_range(start=start_date, end=end_date, freq='D')
        return pd.Series(0.03 / 252, index=dates)
    
    def _get_style_factors(self, stock_list, start_date, end_date):
        """获取风格因子数据"""
        from pymongo import MongoClient
        client = MongoClient(self.mongo_uri)
        db = client[self.db_name]
        
        factors = {}
        for factor_name in ['size', 'value', 'momentum', 'liquidity', 'volatility']:
            data = list(db['style_factors'].find({
                'factor_name': factor_name,
                'ts_code': {'$in': stock_list},
                'trade_date': {'$gte': int(start_date), '$lte': int(end_date)}
            }))
            if data:
                df = pd.DataFrame(data)
                df.set_index(['trade_date', 'ts_code'], inplace=True)
                factors[factor_name] = df['factor_value'].unstack()
        
        client.close()
        
        if factors:
            return pd.concat(factors.values(), axis=1)
        return pd.DataFrame()
    
    def _get_industry_factors(self, stock_list):
        """获取行业分类"""
        from pymongo import MongoClient
        client = MongoClient(self.mongo_uri)
        db = client[self.db_name]
        
        data = list(db['stock_industry'].find({
            'ts_code': {'$in': stock_list}
        }))
        
        client.close()
        
        if data:
            df = pd.DataFrame(data)
            df.set_index('ts_code', inplace=True)
            return df['industry_name']
        return pd.Series()
